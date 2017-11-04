
from ethereum.tools import tester
from datetime import timedelta
from utils import longToHexString, stringToBytes, bytesToHexString
from pytest import fixture, raises
from ethereum.tools.tester import ABIContract, TransactionFailed


def test_market_creation(localFixture, mockUniverse, mockReportingWindow, mockCash, chain, constants, mockMarket, mockReputationToken, mockShareToken, mockShareTokenFactory):
    numTicks = 10 ** 10
    fee = 1
    oneEther = 10 ** 18
    endTime = chain.head_state.timestamp + constants.DESIGNATED_REPORTING_DURATION_SECONDS()
    market = localFixture.upload('../source/contracts/reporting/Market.sol', 'market')
    market.setController(localFixture.contracts["Controller"].address)
    with raises(TransactionFailed, message="outcomes has to be greater than 1"):
        market.initialize(mockReportingWindow.address, endTime, 1, numTicks, fee, mockCash.address, tester.a1, tester.a1)

    with raises(TransactionFailed, message="outcomes has to be less than 9"):
        market.initialize(mockReportingWindow.address, endTime, 9, numTicks, fee, mockCash.address, tester.a1, tester.a1)

    with raises(TransactionFailed, message="numTicks needs to be divisable by outcomes"):
        market.initialize(mockReportingWindow.address, endTime, 7, numTicks, fee, mockCash.address, tester.a1, tester.a1)

    with raises(TransactionFailed, message="fee per eth can not be greater than max fee per eth in attoEth"):
        market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 5, mockCash.address, tester.a1, tester.a1)

    with raises(TransactionFailed, message="creator address can not be 0"):
        market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 5, mockCash.address, longToHexString(0), tester.a1)

    with raises(TransactionFailed, message="designated reporter address can not be 0"):
        market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 5, mockCash.address, tester.a1, longToHexString(0))

    mockUniverse.setForkingMarket(mockMarket.address)
    mockReportingWindow.setUniverse(mockUniverse.address)
    with raises(TransactionFailed, message="forking market address has to be 0"):
        market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 5, mockCash.address, tester.a1, tester.a1)

    mockUniverse.setForkingMarket(longToHexString(0))
    mockReputationToken.setBalanceOf(0)
    mockUniverse.setDesignatedReportNoShowBond(100)
    mockReportingWindow.setReputationToken(mockReputationToken.address)
    with raises(TransactionFailed, message="reporting window reputation token does not have enough balance"):
        market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 5, mockCash.address, tester.a1, tester.a1)
    
    mockReputationToken.setBalanceOf(100)
    mockUniverse.setTargetReporterGasCosts(15)
    mockUniverse.setValidityBond(12)
    with raises(TransactionFailed, message="refund is not over 0"):
        market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 5, mockCash.address, tester.a1, tester.a1, value=0)

    mockShareTokenFactory.resetCreateShareToken();
    assert market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 16, mockCash.address, tester.a1, tester.a2, value=100)
    assert mockShareTokenFactory.getCreateShareTokenMarketValue() == market.address
    assert mockShareTokenFactory.getCreateShareTokenOutcomeValue() == 5 - 1 # mock logs the last outcome
    assert market.getTypeName() == stringToBytes("Market")
    assert market.getUniverse() == mockUniverse.address
    assert market.getReportingWindow() == mockReportingWindow.address
    assert market.getDesignatedReporter() == bytesToHexString(tester.a2)
    assert market.getNumberOfOutcomes() == 5
    assert market.getEndTime() == endTime
    assert market.getNumTicks() == numTicks
    assert market.getDenominationToken() == mockCash.address
    assert market.getMarketCreatorSettlementFeeDivisor() == oneEther / 16
    assert mockShareTokenFactory.getCreateShareTokenCounter() == 5;
    assert mockShareTokenFactory.getCreateShareToken(0) == market.getShareToken(0)
    assert mockShareTokenFactory.getCreateShareToken(1) == market.getShareToken(1)
    assert mockShareTokenFactory.getCreateShareToken(2) == market.getShareToken(2)
    assert mockShareTokenFactory.getCreateShareToken(3) == market.getShareToken(3)
    assert mockShareTokenFactory.getCreateShareToken(4) == market.getShareToken(4)
    
def test_market_decrease_market_creator_settlement_fee(localFixture, initializeMarket, mockMarket):
    oneEther = 10 ** 18

    with raises(TransactionFailed, message="method needs to be called from onlyOwner"):
        initializeMarket.decreaseMarketCreatorSettlementFeeInAttoethPerEth(55, sender=tester.k4)

    with raises(TransactionFailed, message="new fee divisor needs to be greater than fee divisor"):
        initializeMarket.decreaseMarketCreatorSettlementFeeInAttoethPerEth(55, sender=tester.k1)

    assert initializeMarket.getMarketCreatorSettlementFeeDivisor() == oneEther / 16
    assert initializeMarket.decreaseMarketCreatorSettlementFeeInAttoethPerEth(15, sender=tester.k1)
    assert initializeMarket.getMarketCreatorSettlementFeeDivisor() == oneEther / 15

def test_market_designated_report(localFixture, mockUniverse, chain, initializeMarket, mockStakeToken, mockStakeTokenFactory, mockReportingWindow, mockReputationToken):
    with raises(TransactionFailed, message="market is not in designated reporting state"):
        initializeMarket.designatedReport()
    
    chain.head_state.timestamp = initializeMarket.getDesignatedReportDueTimestamp() - 1
    with raises(TransactionFailed, message="designated report method needs to be called from StakeToken"):
        initializeMarket.designatedReport()

    with raises(TransactionFailed, message="StakeToken needs to be contained by market"):
        mockStakeToken.callMarketDesignatedReport(initializeMarket.address)
    
    numTicks = 10 ** 10
    payoutDesignatedNumerators = [numTicks, 0, 0, 0, 0]
    push_to_designated_report_state(localFixture, mockUniverse, chain, initializeMarket, mockStakeToken, payoutDesignatedNumerators, mockStakeTokenFactory, mockReportingWindow, mockReputationToken)

def test_market_dispute_report_with_attoeth(localFixture, constants, initializeMarket, chain, mockUniverse, mockDisputeBond, mockDisputeBondFactory, mockStakeToken, mockStakeTokenFactory, mockReportingWindow, mockReputationToken, mockAugur):
    numTicks = 10 ** 10
    payoutDesignatedNumerators = [numTicks, 0, 0, 0, 0]
    payoutSecondNumeratorsDispute = [0, numTicks, 0, 0, 0]
    with raises(TransactionFailed, message="market needs to be in DESIGNATED_DISPUTE state"):
        initializeMarket.disputeDesignatedReport(payoutDesignatedNumerators, 100, False)
    
    chain.head_state.timestamp = initializeMarket.getDesignatedReportDueTimestamp() - 1
    push_to_designated_report_state(localFixture, mockUniverse, chain, initializeMarket, mockStakeToken, payoutDesignatedNumerators, mockStakeTokenFactory, mockReportingWindow, mockReputationToken)
    mockReportingWindow.reset()
    mockDisputeBondFactory.setCreateDisputeBond(mockDisputeBond.address)
    payoutDesignatedHashValue = initializeMarket.derivePayoutDistributionHash(payoutSecondNumeratorsDispute, False)
    disputeStakeToken = set_mock_stake_token_value(localFixture, initializeMarket, payoutSecondNumeratorsDispute, mockStakeTokenFactory)

    bondAmount = constants.DESIGNATED_REPORTER_DISPUTE_BOND_AMOUNT()
    stakeAmount = initializeMarket.getTotalStake()
    beforeAmount = initializeMarket.getExtraDisputeBondRemainingToBePaidOut()
    tentWinningHash = initializeMarket.getTentativeWinningPayoutDistributionHash()
    assert initializeMarket.getReportingState() == constants.DESIGNATED_DISPUTE()    

    with raises(TransactionFailed, message="tentative winning payout distro can not be 0 for stake token"):
        initializeMarket.disputeDesignatedReport(payoutSecondNumeratorsDispute, 0, False, sender=tester.k2)

    # execute disputeDesignatedReport on market
    assert initializeMarket.disputeDesignatedReport(payoutSecondNumeratorsDispute, 100, False, sender=tester.k2)
    assert mockReportingWindow.getUpdateMarketPhaseCalled() == True
    assert mockReportingWindow.getIncreaseTotalStakeCalled() == True
    assert mockAugur.logReportsDisputedCalled() == True

    assert mockReputationToken.getTrustedTransferSourceValue() == bytesToHexString(tester.a2)
    assert mockReputationToken.getTrustedTransferDestinationValue() == mockDisputeBond.address
    assert mockReputationToken.getTrustedTransferAttotokensValue() == bondAmount

    assert initializeMarket.getExtraDisputeBondRemainingToBePaidOut() == beforeAmount + bondAmount
    assert initializeMarket.getTotalStake() == stakeAmount + bondAmount
    assert initializeMarket.getDesignatedReporterDisputeBond() == mockDisputeBond.address

    assert mockDisputeBondFactory.getCreateDisputeBondMarket() == initializeMarket.address
    assert mockDisputeBondFactory.getCreateDisputeBondBondHolder() == bytesToHexString(tester.a2)
    assert mockDisputeBondFactory.getCreateDisputeBondAmountValue() == bondAmount
    assert mockDisputeBondFactory.getCreateDisputeBondPayoutDistributionHash() == tentWinningHash

    assert disputeStakeToken.getTrustedBuyAddressValue() == bytesToHexString(tester.a2)
    assert disputeStakeToken.getTrustedBuyAttoTokensValue() == 100


def test_market_dispute_report_with_no_attoeth(localFixture, constants, initializeMarket, chain, mockUniverse, mockDisputeBond, mockDisputeBondFactory, mockStakeToken, mockStakeTokenFactory, mockReportingWindow, mockReputationToken, mockAugur):
    numTicks = 10 ** 10
    payoutDesignatedNumerators = [numTicks, 0, 0, 0, 0]
    payoutdNumeratorsDispute = [0, numTicks, 0, 0, 0]
    payoutFirstDisputeNumeratorsDispute = [0, 0, numTicks, 0, 0]
    with raises(TransactionFailed, message="market needs to be in DESIGNATED_DISPUTE state"):
        initializeMarket.disputeDesignatedReport(payoutDesignatedNumerators, 100, False)
    
    chain.head_state.timestamp = initializeMarket.getDesignatedReportDueTimestamp() - 1
    push_to_designated_report_state(localFixture, mockUniverse, chain, initializeMarket, mockStakeToken, payoutDesignatedNumerators, mockStakeTokenFactory, mockReportingWindow, mockReputationToken)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == stringToBytes("")
    # set value for original designated report so that calcuations for tent. winning token doesn't blow up
    mockStakeToken.setTotalSupply(105)
    mockDisputeStakeToken = set_mock_stake_token_value(localFixture, initializeMarket, payoutdNumeratorsDispute, mockStakeTokenFactory)
    mockDisputeStakeToken.setTotalSupply(100)
    assert initializeMarket.getReportingState() == constants.DESIGNATED_DISPUTE()
    mockDisputeBondFactory.setCreateDisputeBond(mockDisputeBond.address)
    # execute disputeDesignatedReport on market
    assert initializeMarket.disputeDesignatedReport(payoutdNumeratorsDispute, 0, False, sender=tester.k2)
    # execution path is same as with attoeth except no stake token transfer
    assert mockDisputeStakeToken.getTrustedBuyAddressValue() == longToHexString(0)
    assert mockDisputeStakeToken.getTrustedBuyAttoTokensValue() == 0

    bondAmount = constants.FIRST_REPORTERS_DISPUTE_BOND_AMOUNT()
    stakeAmount = initializeMarket.getTotalStake()
    beforeAmount = initializeMarket.getExtraDisputeBondRemainingToBePaidOut()

    # might as well test first dispute
    mockReportingWindow.setEndTime(chain.head_state.timestamp + constants.DESIGNATED_REPORTING_DURATION_SECONDS())
    chain.head_state.timestamp = initializeMarket.getDesignatedReportDisputeDueTimestamp() - 1

    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == stringToBytes("")

    mockFirstDisputeStakeToken = set_mock_stake_token_value(localFixture, initializeMarket, payoutFirstDisputeNumeratorsDispute, mockStakeTokenFactory)
    mockFirstDisputeStakeToken.setTotalSupply(10)
    mockReportingWindow.setIsDisputeActive(True)
    assert initializeMarket.getReportingState() == constants.FIRST_DISPUTE()

    mockFirstDisputeBond = localFixture.upload('solidity_test_helpers/MockDisputeBond.sol', 'mockFirstDisputeBond');
    mockDisputeBondFactory.setCreateDisputeBond(mockFirstDisputeBond.address)
    mockNextReportingWindow = localFixture.upload('solidity_test_helpers/MockReportingWindow.sol', 'mockNextReportingWindow');
    mockUniverse.setNextReportingWindow(mockNextReportingWindow.address)

    # execute disputeFirstReporters on market
    assert initializeMarket.disputeFirstReporters(payoutFirstDisputeNumeratorsDispute, 14, False, sender=tester.k3)

    assert mockReputationToken.getTrustedTransferSourceValue() == bytesToHexString(tester.a3)
    assert mockReputationToken.getTrustedTransferDestinationValue() == mockFirstDisputeBond.address
    assert mockReputationToken.getTrustedTransferAttotokensValue() == bondAmount
    
    assert mockNextReportingWindow.getMigrateMarketInFromSiblingCalled() == True
    assert mockReportingWindow.getIncreaseTotalStakeCalled() == True
    assert mockReportingWindow.getRemoveMarketCalled() == True
    assert mockReportingWindow.getUpdateMarketPhaseCalled() == True

    assert initializeMarket.getFirstReportersDisputeBond() == mockFirstDisputeBond.address
 
    assert mockFirstDisputeStakeToken.getTrustedBuyAddressValue() == bytesToHexString(tester.a3)
    assert mockFirstDisputeStakeToken.getTrustedBuyAttoTokensValue() == 14
    payoutFirstDisputeHashDisputeValue = initializeMarket.derivePayoutDistributionHash(payoutFirstDisputeNumeratorsDispute, False)
    # mimic stake token call update tentative winning payout after internal dispute report is called
    assert mockFirstDisputeStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutFirstDisputeHashDisputeValue)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutFirstDisputeNumeratorsDispute, False)

def test_market_update_tentative_winning_payout(localFixture, constants, initializeMarket, chain, mockUniverse, mockDisputeBond, mockDisputeBondFactory, mockStakeToken, mockStakeTokenFactory, mockReportingWindow, mockReputationToken, mockAugur):
    numTicks = 10 ** 10
    payoutDesignatedNumerators = [numTicks, 0, 0, 0, 0]
    payoutSecondNumeratorsDispute = [0, numTicks, 0, 0, 0]
    payoutThridNumerators = [0, 0, numTicks, 0, 0]
    payoutFourthNumerators = [0, 0, 0, numTicks, 0]

    payoutDesignatedHashValue = initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    payoutSecondHashDisputeValue = initializeMarket.derivePayoutDistributionHash(payoutSecondNumeratorsDispute, False)
    payoutThridHashValue = initializeMarket.derivePayoutDistributionHash(payoutThridNumerators, False)
    payoutFourthHashValue = initializeMarket.derivePayoutDistributionHash(payoutFourthNumerators, False)

    chain.head_state.timestamp = initializeMarket.getDesignatedReportDueTimestamp() - 1    
    push_to_designated_report_state(localFixture, mockUniverse, chain, initializeMarket, mockStakeToken, payoutDesignatedNumerators, mockStakeTokenFactory, mockReportingWindow, mockReputationToken)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    
    mockReportingWindow.reset()
    mockDisputeBondFactory.setCreateDisputeBond(mockDisputeBond.address)
    # get second token
    mockSecondStakeToken = set_mock_stake_token_value(localFixture, initializeMarket, payoutSecondNumeratorsDispute, mockStakeTokenFactory)
    
    # verify stake tokens are set
    assert initializeMarket.getStakeToken(payoutDesignatedNumerators, False) == mockStakeToken.address
    assert initializeMarket.getStakeToken(payoutSecondNumeratorsDispute, False) == mockSecondStakeToken.address

    with raises(TransactionFailed, message="tentative winning payout distro can not be 0 we need stake token with positive supply"):
        mockSecondStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutSecondHashDisputeValue)
    
    mockStakeToken.setTotalSupply(105)
    mockSecondStakeToken.setTotalSupply(20)
    assert initializeMarket.getTotalStake() == 0
    assert mockSecondStakeToken.callIncreaseTotalStake(initializeMarket.address, 20)
    assert initializeMarket.getTotalStake() == 20
    assert mockReportingWindow.getIncreaseTotalStakeCalled() == True

    assert mockSecondStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutSecondHashDisputeValue)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutSecondNumeratorsDispute, False)
    # buy a thrid 
    mockThridStakeToken = set_mock_stake_token_value(localFixture, initializeMarket, payoutThridNumerators, mockStakeTokenFactory)
    mockThridStakeToken.setTotalSupply(200)    

    assert initializeMarket.getPayoutDistributionHashStake(payoutDesignatedHashValue) == 105
    assert initializeMarket.getPayoutDistributionHashStake(payoutSecondHashDisputeValue) == 20
    assert initializeMarket.getPayoutDistributionHashStake(payoutThridHashValue) == 200

    assert mockThridStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutThridHashValue)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutThridNumerators, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)

    # bump up existing stake token supply
    mockSecondStakeToken.setTotalSupply(500)
    assert mockSecondStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutSecondHashDisputeValue)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutSecondNumeratorsDispute, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutThridNumerators, False)

    # stake token to rule them all
    mockFourthStakeToken = set_mock_stake_token_value(localFixture, initializeMarket, payoutFourthNumerators, mockStakeTokenFactory)
    mockFourthStakeToken.setTotalSupply(800)    
    assert mockFourthStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutFourthHashValue)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutFourthNumerators, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutSecondNumeratorsDispute, False)

    mockFourthStakeToken.setTotalSupply(0)    
    assert mockFourthStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutFourthHashValue)
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == initializeMarket.derivePayoutDistributionHash(payoutSecondNumeratorsDispute, False)
    assert initializeMarket.getBestGuessSecondPlaceTentativeWinningPayoutDistributionHash() == stringToBytes("")

    mockSecondStakeToken.setTotalSupply(0)
    with raises(TransactionFailed, message="can not withdraw stake token supply it leaves no tentative winning payout"):
        mockSecondStakeToken.callUpdateTentativeWinningPayoutDistributionHash(initializeMarket.address, payoutSecondHashDisputeValue)

def test_market_get_payout_distr_hash_stake(localFixture, initializeMarket, mockStakeTokenFactory):
    numTicks = 10 ** 10
    mockStakeToken_1 = set_mock_stake_token_value(localFixture, initializeMarket, [numTicks, 0, 0, 0, 0], mockStakeTokenFactory)
    mockStakeToken_1.setTotalSupply(80)    
    assert initializeMarket.getPayoutDistributionHashStake(mockStakeToken_1.getPayoutDistributionHash()) == 80

    mockStakeToken_2 = set_mock_stake_token_value(localFixture, initializeMarket, [0, numTicks, 0, 0, 0], mockStakeTokenFactory)
    mockStakeToken_2.setTotalSupply(30)    
    assert initializeMarket.getPayoutDistributionHashStake(mockStakeToken_2.getPayoutDistributionHash()) == 30

    mockStakeToken_3 = set_mock_stake_token_value(localFixture, initializeMarket, [0, 0, numTicks, 0, 0], mockStakeTokenFactory)
    mockStakeToken_3.setTotalSupply(100)    
    assert initializeMarket.getPayoutDistributionHashStake(mockStakeToken_3.getPayoutDistributionHash()) == 100

# create stake token and association with market
def set_mock_stake_token_value(localFixture, initializeMarket, payoutDesignatedNumerators, mockStakeTokenFactory):
    payoutDesignatedHashValue = initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    mockSecondStakeToken = localFixture.upload('solidity_test_helpers/MockStakeToken.sol', str(payoutDesignatedHashValue));
    mockSecondStakeToken.setPayoutDistributionHash(payoutDesignatedHashValue)
    mockStakeTokenFactory.setStakeToken(payoutDesignatedHashValue, mockSecondStakeToken.address)
    assert initializeMarket.getStakeToken(payoutDesignatedNumerators, False) == mockSecondStakeToken.address
    return mockSecondStakeToken

def push_to_designated_report_state(localFixture, mockUniverse, chain, initializeMarket, mockStakeToken, payoutDesignatedNumerators, mockStakeTokenFactory, mockReportingWindow, mockReputationToken):
    payoutDesignatedHashValue = initializeMarket.derivePayoutDistributionHash(payoutDesignatedNumerators, False)
    mockStakeToken.setPayoutDistributionHash(payoutDesignatedHashValue)
    mockStakeTokenFactory.setStakeToken(payoutDesignatedHashValue, mockStakeToken.address)

    assert initializeMarket.getStakeToken(payoutDesignatedNumerators, False)
    assert mockStakeTokenFactory.getCreateDistroHashValue() == payoutDesignatedHashValue
    assert mockStakeTokenFactory.getCreateStakeTokenMarketValue() == initializeMarket.address
    assert mockStakeTokenFactory.getCreateStakeTokenPayoutValue() == payoutDesignatedNumerators
    assert initializeMarket.getStakeToken(payoutDesignatedNumerators, False) == mockStakeToken.address

    mockReportingWindow.setReputationToken(mockReputationToken.address)
    mockReputationToken.setBalanceOf(105)
    ownerBalance = chain.head_state.get_balance(tester.a1)

    assert mockStakeToken.callMarketDesignatedReport(initializeMarket.address)
    assert initializeMarket.getDesignatedReportReceivedTime() == chain.head_state.timestamp
    assert initializeMarket.getTentativeWinningPayoutDistributionHash() == mockStakeToken.getPayoutDistributionHash()
    assert mockReportingWindow.getUpdateMarketPhaseCalled() == True
    assert mockReportingWindow.getNoteDesignatedReport() == True
    assert mockReputationToken.getTransferValueFor(tester.a1) == 105
    assert chain.head_state.get_balance(tester.a1) == ownerBalance + mockUniverse.getTargetReporterGasCosts()

@fixture(scope="session")
def localSnapshot(fixture, augurInitializedWithMocksSnapshot):
    fixture.resetToSnapshot(augurInitializedWithMocksSnapshot)
    controller = fixture.contracts['Controller']
    mockReportingParticipationTokenFactory = fixture.contracts['MockParticipationTokenFactory']
    mockDisputeBondFactory = fixture.contracts['MockDisputeBondFactory']
    mockCash = fixture.contracts['MockCash']
    mockAugur = fixture.contracts['MockAugur']
    mockShareTokenFactory = fixture.contracts['MockShareTokenFactory']    
    mockShareToken = fixture.contracts['MockShareToken']
    mockFillOrder = fixture.contracts['MockFillOrder']
    mockStakeTokenFactory = fixture.contracts['MockStakeTokenFactory']

    # pre populate share tokens for max of 8 possible outcomes
    for index in range(8):
        item = fixture.upload('solidity_test_helpers/MockShareToken.sol', 'newMockShareToken' + str(index));
        mockShareTokenFactory.pushCreateShareToken(item.address)
    
    #mockMapFactory = fixture.contracts['MockMapFactory']
    # TODO: remove MockMapFactory probably don't need it
    #controller.setValue(stringToBytes('MapFactory'), mockMapFactory.address)
    controller.setValue(stringToBytes('Cash'), mockCash.address)
    controller.setValue(stringToBytes('ParticipationTokenFactory'), mockReportingParticipationTokenFactory.address)
    controller.setValue(stringToBytes('ShareTokenFactory'), mockShareTokenFactory.address)
    controller.setValue(stringToBytes('FillOrder'), mockShareTokenFactory.address)    
    controller.setValue(stringToBytes('StakeTokenFactory'), mockStakeTokenFactory.address)    
    controller.setValue(stringToBytes('DisputeBondFactory'), mockDisputeBondFactory.address)    
    mockShareTokenFactory.resetCreateShareToken();
    return fixture.createSnapshot()

@fixture
def localFixture(fixture, localSnapshot):
    fixture.resetToSnapshot(localSnapshot)
    return fixture

@fixture
def mockUniverse(localFixture):
    return localFixture.contracts['MockUniverse']

@fixture
def mockReportingWindow(localFixture):
    mockReportingWindow = localFixture.contracts['MockReportingWindow']
    mockReportingWindow.reset()
    return mockReportingWindow

@fixture
def constants(localFixture):
    return localFixture.contracts['Constants']

@fixture
def mockCash(localFixture):
    return localFixture.contracts['MockCash']

@fixture
def chain(localFixture):
    return localFixture.chain

@fixture
def mockMarket(localFixture):
    return localFixture.contracts['MockMarket']

@fixture
def mockAugur(localFixture):
    mockAugur = localFixture.contracts['MockAugur']
    mockAugur.reset()
    return mockAugur

@fixture
def mockReputationToken(localFixture):
    mockReputationToken = localFixture.contracts['MockReputationToken']
    mockReputationToken.reset()
    return mockReputationToken

@fixture
def mockShareToken(localFixture):
    return localFixture.contracts['MockShareToken']

@fixture
def mockStakeTokenFactory(localFixture):
    mockStakeTokenFactory = localFixture.contracts['MockStakeTokenFactory']
    mockStakeTokenFactory.initializeMap(localFixture.contracts['Controller'].address)
    return mockStakeTokenFactory

@fixture
def mockShareTokenFactory(localFixture):
    return localFixture.contracts['MockShareTokenFactory']

@fixture
def mockStakeToken(localFixture):
    return localFixture.contracts['MockStakeToken']

@fixture
def mockMapFactory(localFixture):
    return localFixture.contracts['MockMapFactory']

@fixture
def mockDisputeBond(localFixture):
    return localFixture.contracts['MockDisputeBond']

@fixture
def mockDisputeBondFactory(localFixture):
    return localFixture.contracts['MockDisputeBondFactory']

@fixture
def initializeMarket(localFixture, mockReportingWindow, mockUniverse, mockReputationToken, chain, constants, mockCash, mockMapFactory):
    market = localFixture.upload('../source/contracts/reporting/Market.sol', 'market')
    contractMap = localFixture.upload('../source/contracts/libraries/collections/Map.sol', 'Map')
    numTicks = 10 ** 10
    fee = 1
    endTime = chain.head_state.timestamp + constants.DESIGNATED_REPORTING_DURATION_SECONDS()
    market.setController(localFixture.contracts["Controller"].address)

    mockMapFactory.setMap(contractMap.address)
    mockUniverse.setForkingMarket(longToHexString(0))
    mockUniverse.setDesignatedReportNoShowBond(100)
    mockReportingWindow.setReputationToken(mockReputationToken.address)
    mockReputationToken.setBalanceOf(100)
    mockUniverse.setTargetReporterGasCosts(15)
    mockUniverse.setValidityBond(12)
    mockReportingWindow.setUniverse(mockUniverse.address)
    assert market.initialize(mockReportingWindow.address, endTime, 5, numTicks, 16, mockCash.address, tester.a1, tester.a2, value=100)
    return market