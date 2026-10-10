from Packets.Messages.Client.StartSecureConnectionMessage import *
from Packets.Messages.Client.LoginMessage import *
from Packets.Messages.Client.GoHomeMessage import *
from Packets.Messages.Client.EndClientTurnMessage import *
from Packets.Messages.Client.ChangeAccountSettingsMessage import *
from Packets.Messages.Client.VisitAIMessage import *

availablePackets = {

    10122: StartSecureConnectionMessage,
    10101: LoginMessage,
    10104: ChangeAccountSettingsMessage,
    14101: GoHomeMessage,
    14102: EndClientTurnMessage,
    14112: VisitAIMessage,

}
