"""Authoritative message ids recovered from the client binary.

The numbers below come from ``LogicSoilMessageFactory::createMessageByType``
and every ``<Message>::getMessageType()`` in ``Hay Day.i64`` (IDA / Hex-Rays,
see ``tools/decode_macho.py``).  They replace the guesses in the server's
message scaffolds: a message declared with the wrong id is silently ignored
by the client, which makes a feature look "implemented" while doing nothing.

Ids in the 10xxx / 14xxx range are client -> server, 20xxx / 24xxx are
server -> client; helper/billing messages use the 19xxx / 29xxx ranges.
"""
MESSAGE_IDS = {
    "LoginMessage": 10101,
    "AvatarInfoRequestMessage": 10102,
    "AvatarInfoListRequestMessage": 10103,
    "ChangeAccountSettingsMessage": 10104,
    "ClientCapabilitiesMessage": 10107,
    "StartSecureConnectionMessage": 10122,

    "GoHomeMessage": 14101,
    "EndClientTurnMessage": 14102,
    "TrackingMessage": 14103,
    "AskForTargetHomeListMessage": 14104,
    "VisitHomeMessage": 14108,
    "ChangeHomeNameMessage": 14109,
    "BuyFromStandMessage": 14110,
    "NewspaperDataRequestMessage": 14111,
    "VisitAIMessage": 14112,
    "GetFollowerListMessage": 14113,
    "FollowFarmMessage": 14114,
    "StopFollowFarmMessage": 14115,
    "AIBoughtFromStandMessage": 14116,
    "GetFollowingListMessage": 14118,
    "DisconnectMessage": 14119,
    "GetFollowerCountMessage": 14120,
    "HelpWithBoatOrderMessage": 14121,

    "AvatarInfoResponseMessage": 20102,
    "LoginFailedMessage": 20103,
    "LoginOkMessage": 20104,
    "FriendListMessage": 20105,
    "NotifyPurchaseMessage": 20106,
    "NotifyOnSaleMessage": 20107,
    "NotifyOnThirdPartyPurchaseMessage": 20108,
    "GetFollowingListResponseMessage": 20109,
    "NotifyVisitorsOnBoatHelpReceivedMessage": 20110,
    "NotifyOnBoatHelpRequestedMessage": 20111,
    "NotifyOnBoatHelpReceivedMessage": 20112,
    "NotifyVisitorsOnWholeBoatOrderCompleteMessage": 20113,
    "FriendMetaMessage": 20114,
    "AvatarInfoListResponseMessage": 20116,
    "SecureConnectionOKMessage": 20122,
    "SecureConnectionFailedMessage": 20123,

    "OwnHomeDataMessage": 24101,
    "OtherHomeDataMessage": 24102,
    "BuyFromStandResponseMessage": 24103,
    "ChangeHomeNameResponseMessage": 24104,
    "TargetHomeListMessage": 24105,
    "HelpWithBoatOrderResponseMessage": 24106,
    "AdvertisementListMessage": 24110,
    "EndClientTurnOKMessage": 24112,
    "FollowerListMessage": 24113,
    "FollowFarmResponseMessage": 24114,
    "AIHomeDataMessage": 24115,
    "FollowerCountMessage": 24116,
    "ClientOutOfSyncMessage": 24119,

    "FacebookAccountBoundMessage": 24201,
    "FacebookAccountAlreadyBoundMessage": 24202,
    "GamecenterAccountBoundMessage": 24211,
    "GamecenterAccountAlreadyBoundMessage": 24212,

    "BindFacebookAccountMessage": 14201,
    "BindGamecenterAccountMessage": 14211,
    "AskForAddableFriendsMessage": 10503,
    "AskForFriendMetaMessage": 10504,
    "AskForMailListMessage": 10901,
    "MailListMessage": 20903,
    "ShutdownStartedMessage": 20161,

    "AskForProductListMessage": 19998,
    "ProductListMessage": 29998,
    "VerifyBillingReceiptMessage": 19999,
    "ReceiptVerificationMessage": 29999,
}


# Local module names use "Ok" where the client's demangled symbol says "OK".
MESSAGE_IDS.setdefault("SecureConnectionOkMessage", 20122)
MESSAGE_IDS.setdefault("EndClientTurnOkMessage", 24112)


def message_id(name):
    """Id of ``name`` (class or module name), or 0 when not in the binary."""
    return MESSAGE_IDS.get(name, MESSAGE_IDS.get(
        name[:-7] if name.endswith("Message") else name, 0))
