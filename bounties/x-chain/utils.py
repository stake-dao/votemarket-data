import asyncio
import os, json, rlp
import logging
from dotenv import load_dotenv
from web3 import Web3
from w3multicall.multicall import W3Multicall
from hexbytes import HexBytes
from eth_utils import to_checksum_address

from etherscan_service import get_logs_by_address_and_topics
from parquet_cache_service import ParquetCache


logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

load_dotenv()


class Constants:
    ETHEREUM_STATE_SENDER = "0x189B2c0e4e8e221173f266f311C949498A4859D1"
    MAINNET_URL = "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("ALCHEMY_API_KEY")
    ARBITRUM_URL = "https://arb1.arbitrum.io/rpc"
    OPTIMISM_URL = "https://opt-mainnet.g.alchemy.com/v2/" + os.getenv(
        "ALCHEMY_API_KEY"
    )
    BASE_URL = "https://base-mainnet.g.alchemy.com/v2/" + os.getenv("ALCHEMY_API_KEY")
    POLYGON_URL = "https://polygon.llamarpc.com"

    PROTOCOLS = ["curve", "balancer", "frax", "fxn"]

    # To get positions
    GAUGES_SLOTS = {
        "curve": {
            "vote_user_slope": 9,
            "last_user_vote": 11,
            "point_weights": 12,
        },
        "balancer": {
            "vote_user_slope": 1000000005,
            "last_user_vote": 1000000007,
            "point_weights": 1000000008,
        },
        "frax": {
            "vote_user_slope": 1000000008,
            "last_user_vote": 1000000010,
            "point_weights": 10000000011,
        },
        "fxn": {
            "vote_user_slope": 1000000008,
            "last_user_vote": 1000000010,
            "point_weights": 10000000011,
        },
    }

    PLATFORMS = {
        "curve": [
            {
                "chainId": 42161,
                "address": "0xB854cF650F5492d23e52cb2A7a58B787fC25B0Bb",
            },
            {
                "chainId": 10,
                "address": "0x786e2D03B32BFc42D60C366F07aBe9B218B7A4eE",
            },
            {
                "chainId": 137,
                "address": "0x6Bd5A9D7f683Db92F45fEd77b2291139E854bf20",
            },
            {
                "chainId": 8453,
                "address": "0x786e2D03B32BFc42D60C366F07aBe9B218B7A4eE",
            },
        ],
        "balancer": [
            {
                "chainId": 42161,
                "address": "0xFf276AB161f48f6DBa99dE4601f9a518D1d903f9",
            },
            {
                "chainId": 10,
                "address": "0x21e6ABAf84f6087915ffFE6275f9cBeCDeeEC837",
            },
            {
                "chainId": 137,
                "address": "0x6d875483F57E2b85378C74377542eA242Ed46Dbe",
            },
            {
                "chainId": 8453,
                "address": "0x21e6ABAf84f6087915ffFE6275f9cBeCDeeEC837",
            },
        ],
        "frax": [
            {
                "chainId": 42161,
                "address": "0x4941c004dC4Ae7bcb74B404fbd4ff07Dc32e3ecc",
            },
            {
                "chainId": 10,
                "address": "0xa8377e03617de8DA2C18621BE83bcBd5a34Ca1C9",
            },
            {
                "chainId": 137,
                "address": "0x189B2c0e4e8e221173f266f311C949498A4859D1",
            },
            {
                "chainId": 8453,
                "address": "0xa8377e03617de8DA2C18621BE83bcBd5a34Ca1C9",
            },
        ],
        "fxn": [
            {
                "chainId": 42161,
                "address": "0xE5cE02443942B006d0851d6e73d9dbEeE743b88d",
            },
            {
                "chainId": 10,
                "address": "0xCbE04EDe27B30B1C664e777fbF09ae9d62412FD8",
            },
            {
                "chainId": 137,
                "address": "0xf3fD346138C93Cb1c5be1145566e915e54DC5A56",
            },
            {
                "chainId": 8453,
                "address": "0xCbE04EDe27B30B1C664e777fbF09ae9d62412FD8",
            },
        ],
    }

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    }

    CREATION_BLOCKS = {
        "curve": 10647875,
        "balancer": 14457014,
        "frax": 14052749,
        "fxn": 18156185,
    }

    VOTE_EVENT_HASH = (
        "0x45ca9a4c8d0119eb329e580d28fe689e484e1be230da8037ade9547d2d25cc91"
    )

    """ Types """

    ActiveBountyType = {
        "bounty_id": "",
        "reward_token": "",
        "gauge_address": "",
        "blacklist": [],
    }


class Utils:
    @staticmethod
    def get_web3(chainId):
        if chainId == 1:
            return Web3(Web3.HTTPProvider(Constants.MAINNET_URL))
        elif chainId == 42161:
            return Web3(Web3.HTTPProvider(Constants.ARBITRUM_URL))
        elif chainId == 10:
            return Web3(Web3.HTTPProvider(Constants.OPTIMISM_URL))
        elif chainId == 137:
            return Web3(Web3.HTTPProvider(Constants.POLYGON_URL))
        elif chainId == 8453:
            return Web3(Web3.HTTPProvider(Constants.BASE_URL))
        else:
            raise Exception("ChainId not supported")

    @staticmethod
    def load_json(name):
        with open(name + ".json", "r") as f:
            return json.load(f)

    @staticmethod
    def load_contract(w3, address, abi):
        return w3.eth.contract(
            address=to_checksum_address(address),
            abi=abi,
        )

    @staticmethod
    def encode_rlp_proofs(proofs):
        account_proof = list(map(rlp.decode, map(HexBytes, proofs["accountProof"])))
        storage_proofs = [
            list(map(rlp.decode, map(HexBytes, proof["proof"])))
            for proof in proofs["storageProof"]
        ]
        return rlp.encode([account_proof, *storage_proofs])

    @staticmethod
    def get_event_logs(
        w3, contract_address, abi, event_name, from_block, to_block, filters=None
    ):
        contract_address = to_checksum_address(contract_address.lower())
        contract = w3.eth.contract(address=contract_address, abi=Utils.load_json(abi))
        return getattr(contract.events, event_name).getLogs(
            fromBlock=from_block, toBlock=to_block, argument_filters=filters
        )

    """ Votemarket platform """

    @staticmethod
    def get_active_bounties(vm, current_period, w3):
        active_bounties = []
        nextId = vm.functions.nextID().call()
        multicall = W3Multicall(w3)

        # Prepare multicall for all bounties
        for i in range(nextId):
            multicall.add(
                W3Multicall.Call(
                    vm.address,
                    "bounties(uint256)(address,address,address,uint256,uint256,uint256,uint256)",
                    [i],
                )
            )
            multicall.add(
                W3Multicall.Call(
                    vm.address,
                    "upgradeBountyQueue(uint256)(uint256,uint256,uint256,uint256)",
                    [i],
                )
            )
            multicall.add(
                W3Multicall.Call(
                    vm.address,
                    "getBlacklistedAddressesPerBounty(uint256)(address[])",
                    [i],
                )
            )

            # Execute all calls in a single batch
            results = multicall.call()

        # Process results
        for i in range(nextId):
            bounty_details = results[i * 3]
            upgrade_details = results[i * 3 + 1]
            blacklist = results[i * 3 + 2]

            bounty_endTimestamp = bounty_details[4]
            upgraded_bounty_endTimestamp = upgrade_details[3]

            if (
                bounty_endTimestamp > current_period
                or upgraded_bounty_endTimestamp > current_period
            ):
                active_bounties.append(
                    {
                        "platform": vm.address,
                        "bounty_id": i,
                        "reward_token": bounty_details[2],
                        "gauge_address": bounty_details[0],
                        "blacklist": blacklist,
                    }
                )
        return active_bounties

    @staticmethod
    async def query_all_voters_gauges(protocol, gauge_addresses):
        w3 = Utils.get_web3(1)
        current_block = w3.eth.get_block("latest")["number"]

        all_votes = {}

        for gauge_address in gauge_addresses:
            votes = await Utils.query_gauge_votes(
                w3, protocol, gauge_address, current_block
            )
            if gauge_address not in all_votes:
                all_votes[gauge_address] = []
            all_votes[gauge_address].extend([vote["user"] for vote in votes])

        return all_votes

    @staticmethod
    async def query_gauge_votes(w3, protocol, gauge_address, block_number):
        CACHE_DIR = "bounties"
        VOTES_CACHE_FILE = f"{protocol}_votes_cache.parquet"
        cache = ParquetCache(CACHE_DIR)

        start_block_list = cache.get_columns(VOTES_CACHE_FILE, ["latest_block"]).get(
            "latest_block", []
        )
        start_block = (
            start_block_list[0]
            if start_block_list
            else Constants.CREATION_BLOCKS[protocol]
        )

        end_block = block_number
        logging.info(
            f"Getting votes for {gauge_address} from {start_block} to {end_block}"
        )

        if start_block < end_block:
            new_votes = await Utils.fetch_new_votes(
                w3, protocol, start_block, end_block
            )

            cached_data = cache.get_columns(
                VOTES_CACHE_FILE, ["time", "user", "gauge_addr", "weight"]
            )
            cached_votes = [
                {"time": t, "user": u, "gauge_addr": g, "weight": w}
                for t, u, g, w in zip(
                    cached_data["time"],
                    cached_data["user"],
                    cached_data["gauge_addr"],
                    cached_data["weight"],
                )
            ]
            all_votes = cached_votes + new_votes
            cache.save_votes(VOTES_CACHE_FILE, end_block, all_votes)
        else:
            logging.info("Using cached data as start block is not less than end block")
            cached_data = cache.get_columns(
                VOTES_CACHE_FILE, ["time", "user", "gauge_addr", "weight"]
            )
            all_votes = [
                {"time": t, "user": u, "gauge_addr": g, "weight": w}
                for t, u, g, w in zip(
                    cached_data["time"],
                    cached_data["user"],
                    cached_data["gauge_addr"],
                    cached_data["weight"],
                )
            ]

        filtered_votes = [
            vote
            for vote in all_votes
            if vote["gauge_addr"].lower() == gauge_address.lower()
        ]

        return filtered_votes

    @staticmethod
    async def fetch_new_votes(w3, protocol, start_block, end_block):
        INCREMENT = 100_000
        tasks = []

        for block in range(start_block, end_block + 1, INCREMENT):
            current_end_block = min(block + INCREMENT - 1, end_block)
            task = asyncio.create_task(
                Utils.fetch_votes_chunk(w3, protocol, block, current_end_block)
            )
            tasks.append(task)

        chunks = await asyncio.gather(*tasks)
        return [vote for chunk in chunks for vote in chunk]

    @staticmethod
    async def fetch_votes_chunk(w3, protocol, start_block, end_block):
        logging.info(f"Getting logs from {start_block} to {end_block}")
        try:
            votes_logs = get_logs_by_address_and_topics(
                Constants.GAUGE_CONTROLLER[protocol],
                start_block,
                end_block,
                {"0": Constants.VOTE_EVENT_HASH},
            )
            logging.info(f"{len(votes_logs)} votes logs found")
            return [Utils._decode_vote_log(log) for log in votes_logs]
        except Exception as e:
            if "No records found" in str(e):
                logging.info(f"No votes found from {start_block} to {end_block}")
                return []
            else:
                raise

    @staticmethod
    def _decode_vote_log(log):
        data = bytes.fromhex(log["data"][2:])
        try:
            return {
                "time": int.from_bytes(data[0:32], byteorder="big"),
                "user": to_checksum_address("0x" + data[44:64].hex()),
                "gauge_addr": to_checksum_address("0x" + data[76:96].hex()),
                "weight": int.from_bytes(data[96:128], byteorder="big"),
            }
        except ValueError as e:
            raise ValueError(
                f"Error decoding vote log: {str(e)}. Raw data: {log['data']}"
            )

    @staticmethod
    def check_eligibility(w3, gauge_controller, user, gauge_address, current_period):
        # Check if user is eligible for the bounty
        is_eligible = False

        """
        # Check if user is blacklisted on all bounties with that gauge, if not , process
        for bounty in active_bounties:
            if bounty.get("gaugeAddress") == gauge:
                if user not in bounty.get("blacklist"):
                    is_eligible = True
                    break
        """

        # Check the slope of that user for the gauge
        last_vote = gauge_controller.functions.last_user_vote(
            to_checksum_address(user.lower()),
            to_checksum_address(gauge_address.lower()),
        ).call()
        (slope, _, end) = gauge_controller.functions.vote_user_slopes(
            to_checksum_address(user.lower()),
            to_checksum_address(gauge_address.lower()),
        ).call()

        if slope != 0 and current_period < end and current_period > last_vote:
            is_eligible = True

        return is_eligible
