from app.models.investition import Investition
from app.models.lohnkosten import Lohnkosten
from app.models.material import Material
from app.models.maschine import Maschine
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.user import User
from app.models.zuschlagssatz import Zuschlagssatz

__all__ = [
    "User",
    "Material",
    "Maschine",
    "Lohnkosten",
    "Zuschlagssatz",
    "SpritzgussKalkulation",
    "Investition",
]
