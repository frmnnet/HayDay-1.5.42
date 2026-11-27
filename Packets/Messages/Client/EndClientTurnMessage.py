from Utils.Logging import logger
from Utils.Reader import Reader
from Packets.Messages.Server.EndClientTurnOkMessage import EndClientTurnOkMessage
from Packets.Messages.Server.ClientOutOfSyncMessage import ClientOutOfSyncMessage
from Logic.CommandFactory import COMMANDS
from Logic.Commands.LogicCommand import LogicCommand
from Logic.GameState import GameState
from Logic import HomeObjects
from Logic import HomeFields
from Logic.GameTime import now_seconds


class EndClientTurnMessage(Reader):
    ID = 14102
    MAX_COMMANDS = 50  # the client rejects command counts >= 0x33
    OBJECT_ID_FIELDS = {
        "LogicPlantSeedsCommand": (0,),
        "LogicHarvestFieldCommand": (0,),
        "LogicHarvestFieldGainCommand": (0,),
        "LogicHarvestFieldOverCommand": (0,),
        "LogicInstantCompleteFieldCommand": (0,),
        "LogicMoveObjectCommand": (0,),
        "LogicMirrorObjectCommand": (0,),
        "LogicFeedAnimalCommand": (0,),
        "LogicCollectAnimalCommand": (0,),
        "LogicInstantCompleteAnimalCommand": (0,),
        "LogicCollectProductionsCommand": (0,),
        "LogicInstantCompleteBuildingCommand": (0,),
        "LogicCollectCompletedBuildingExpCommand": (0,),
    }
    CREATE_OBJECT_COMMANDS = {
        "LogicBuyObjectCommand",
        "LogicBuyAnimalCommand",
        "LogicBuyExpansionCommand",
        "LogicBuyMarketStandCommand",
    }

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device
        self.subtick = 0
        self.tick = 0
        self.count = 0
        self.commands = []
        self.decode_error = None
        # Dev builds append tick byte streams after the commands:
        #   int32 stream_count; per stream: int32 length + bytes
        # (see EndClientTurnMessage::decode -> LogicVersion::isDev).
        # There is NO trailing checksum in this message.
        self.tick_byte_streams = []

    def decode(self):
        """Real wire framing (see EndClientTurnMessage::decode)::

            int32 subtick
            byte  count (< 0x33)
            per command: byte type + payload (LogicCommand::decode reads
                         a trailing int32 tick inside each command)
            [dev only] int32 stream_count; per stream: int32 len + bytes
        """
        r = self
        try:
            self.subtick = r.readInt()
            count = r.readByte()
        except Exception as e:
            logger.error("EndClientTurnMessage: frame decode error: {}".format(e))
            return
        self.tick = self.subtick
        if count > self.MAX_COMMANDS:
            self.decode_error = "invalid command count {}".format(count)
            return
        self.count = count

        for _ in range(count):
            if r.tell() >= len(r.buffer):
                break
            try:
                cmd_type = r.readByte()
            except Exception:
                break
            handler = COMMANDS.get(cmd_type)
            if handler is None:
                self.decode_error = "unknown command type {}".format(cmd_type)
                logger.warning(
                    "EndClientTurn: unknown command type={} at byte {}; "
                    "previous={}; remaining={}".format(
                        cmd_type, r.tell() - 1,
                        [c.NAME for c in self.commands[-3:]],
                        bytes(r.buffer[r.tell() - 1:]).hex()))
                break
            cmd = handler()
            start = r.tell()
            try:
                cmd.decode_fields(r, handler.FIELDS)
            except Exception as e:
                self.decode_error = "command type {}: {}".format(cmd_type, e)
                logger.error("EndClientTurnMessage: decode error type={}: {}".format(cmd_type, e))
                break
            cmd.payload = bytes(r.buffer[start:r.tell()])
            cmd.raw = cmd.payload.hex()
            self.commands.append(cmd)

        if self.decode_error is None and len(self.commands) != count:
            self.decode_error = "expected {} commands, decoded {}".format(
                count, len(self.commands))
        self._decode_tick_streams(r)

    def _decode_tick_streams(self, r):
        """Parse the optional dev-only tick byte stream block.

        Only accept it when it consumes the remaining bytes exactly; an
        incomplete/garbage tail is left alone so it can't desync commands.
        """
        start = r.tell()
        if start + 4 > len(r.buffer):
            return
        try:
            count = r.readInt()
            if not 0 <= count <= 64:
                r.seek(start)
                return
            streams = []
            for _ in range(count):
                size = r.readInt()
                if size < 0 or r.tell() + size > len(r.buffer):
                    raise ValueError("bad tick stream length %s" % size)
                streams.append(bytes(r.buffer[r.tell():r.tell() + size]))
                r.seek(size, 1)
            if r.tell() != len(r.buffer):
                raise ValueError("trailing garbage after tick streams")
            self.tick_byte_streams = streams
        except Exception:
            self.tick_byte_streams = []
            r.seek(start)

    def process(self):
        if self.decode_error:
            # Command payloads have no length prefix, so parsing one command
            # incorrectly makes every later byte ambiguous.  Never execute a
            # partial turn; ask the client to reload its authoritative state.
            logger.error("[!] EndClientTurn decode failed: {}".format(
                self.decode_error))
            ClientOutOfSyncMessage(self.device).Send()
            return
        # One lock per account: a reconnecting client can have two threads
        # in flight, and interleaving their commands would corrupt the farm.
        state = GameState.for_device(self.device)
        with state.lock:
            # Field maturity is an absolute server deadline.  Advance it at
            # the start of every turn, not only after a reconnect, so a crop
            # whose timer elapsed while the client stayed online is harvestable
            # and a grow command cannot be charged twice for an already-ready
            # field.
            HomeFields.advance(
                state.home.data, state.home.fields, now=now_seconds())
            observed_ids = []
            for command in self.commands:
                indexes = self.OBJECT_ID_FIELDS.get(command.NAME, ())
                for index in indexes:
                    observed_ids.append(command.arg(index, 0))
            for cmd in self.commands:
                try:
                    # A Buy command earlier in this same turn creates the
                    # object referenced by a later Move/Plant command.  Bind
                    # the complete new-object batch after all creators ran
                    # and before the first command that addresses one.
                    if cmd.NAME not in self.CREATE_OBJECT_COMMANDS:
                        HomeObjects.reconcile_runtime_ids(
                            state.home.data, observed_ids)
                    cmd.execute(state)
                except Exception as e:
                    logger.info("[!] execute error {}: {}".format(cmd.NAME, e))
            if self.tick_byte_streams:
                logger.info("[*] EndClientTurn got {} tick byte stream(s)".format(
                    len(self.tick_byte_streams)))
            state.save()
            # The acknowledgement is the client's commit signal.  Persist the
            # whole turn before sending it; otherwise a failed SQLite write
            # leaves the client believing that changes are durable while the
            # next home load restores the previous state.
            if state.dirty and not state.flush():
                logger.error("[DB] turn not acknowledged: persistence failed")
                ClientOutOfSyncMessage(self.device).Send()
                return
        EndClientTurnOkMessage(self.device).Send()
