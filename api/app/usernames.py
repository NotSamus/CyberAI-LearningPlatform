"""Made-up usernames for students, in the style of Xbox gamertags: an adjective, a noun and two to
four digits, such as "swiftfalcon482". Students are known on the platform by their username only
(no real name is stored, see auth.check_name), so an admin can hand out one of these instead of a
username made from the student's name. GET /api/admin/username-suggestion and
`python -m app.manage create-user --random` use it.

The words are kept harmless on their own and side by side: no people, no bodies, no skin colours,
nothing violent, and no animal with a second meaning. Joining two words can still spell something
neither has, so test/api/test_usernames.py checks every adjective and noun pair against BLOCKED.
"""
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

ADJECTIVES = (
    "agile", "amber", "atomic", "azure", "brave", "breezy", "bright", "brisk", "calm", "clever",
    "cobalt", "cosmic", "crimson", "crisp", "cyber", "daring", "digital", "eager", "electric", "emerald",
    "epic", "frosty", "gentle", "gleaming", "golden", "humble", "icy", "indigo", "jade", "jolly",
    "keen", "kind", "lively", "lucky", "lunar", "magnetic", "mellow", "mighty", "misty", "mystic",
    "nimble", "noble", "orbital", "polar", "quantum", "quick", "quiet", "radiant", "rapid", "rustic",
    "silent", "silver", "sleek", "snowy", "solar", "sonic", "spry", "stellar", "stormy", "sunny",
    "swift", "tidal", "turbo", "valiant", "vibrant", "vivid", "wise", "witty", "zesty", "zippy",
)

NOUNS = (
    "acorn", "aurora", "badger", "beacon", "bison", "blizzard", "breeze", "cactus", "canyon", "cedar",
    "cheetah", "cipher", "circuit", "comet", "condor", "coyote", "crystal", "cyclone", "dolphin", "ember",
    "falcon", "firefly", "gecko", "geyser", "glacier", "griffin", "harbor", "hawk", "heron", "jaguar",
    "kernel", "kestrel", "koala", "lantern", "lemur", "lynx", "mantis", "maple", "meadow", "meteor",
    "moose", "narwhal", "nebula", "orbit", "orca", "osprey", "panda", "pelican", "penguin", "photon",
    "pixel", "prism", "puffin", "pulsar", "quartz", "quasar", "raven", "rocket", "sparrow", "summit",
    "thunder", "tiger", "tornado", "toucan", "tundra", "turtle", "vector", "volcano", "willow", "zebra",
)

# Never part of a suggestion, wherever it would fall: across the joint of two words, or in the digits.
BLOCKED = (
    "anal", "anus", "arse", "ass", "bitch", "boob", "butt", "chink", "cock", "coon", "crap", "cum",
    "cunt", "damn", "dick", "die", "dyke", "fag", "fart", "fuck", "gay", "gook", "hell", "hoe", "homo",
    "jew", "jizz", "kike", "kill", "kkk", "milf", "nazi", "nig", "nude", "pedo", "pee", "penis", "piss",
    "poo", "porn", "pube", "rape", "sex", "shit", "slut", "spic", "suck", "tard", "thot", "tit", "turd",
    "twat", "vag", "wank", "whore",
    "69", "88", "420", "666",
)


def _made_up() -> str:
    """One adjective, one noun, and two to four digits not starting with 0."""
    length = secrets.choice((2, 3, 4))
    digits = str(10 ** (length - 1) + secrets.randbelow(9 * 10 ** (length - 1)))
    return secrets.choice(ADJECTIVES) + secrets.choice(NOUNS) + digits


def suggest(db: Session, tries: int = 50) -> str:
    """A username nobody has yet. Two admins may be handed the same one at the same moment: the
    second to create it is told it is taken (auth.create_user), and asks for another."""
    for _ in range(tries):
        username = _made_up()
        if any(word in username for word in BLOCKED):
            continue
        if db.scalar(select(User.id).where(User.username == username)) is None:
            return username
    raise RuntimeError(f"No free username was found in {tries} tries.")
