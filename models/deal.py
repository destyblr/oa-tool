from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Deal:
    # Identification
    asin: str
    titre: str
    categorie: str
    bsr_fr: Optional[int] = None

    # Statut
    statut: str = "UNKNOWN"  # ELIGIBLE / RESTRICTED / HAZMAT
    nb_vendeurs_fba: int = 0
    amazon_en_stock: bool = False

    # Prix par marketplace
    buy_box_fr: Optional[float] = None
    buy_box_de: Optional[float] = None
    buy_box_it: Optional[float] = None
    buy_box_es: Optional[float] = None
    buy_box_90j_moy_fr: Optional[float] = None
    buy_box_90j_min_fr: Optional[float] = None

    # Frais
    referral_fee: Optional[float] = None
    frais_fba: Optional[float] = None
    frais_efn: Optional[float] = None
    envoi_fba: Optional[float] = None
    urssaf: Optional[float] = None
    total_frais: Optional[float] = None

    # Rentabilité
    marketplace_recommandee: Optional[str] = None
    roi_fr: Optional[float] = None
    roi_meilleur: Optional[float] = None
    gain_vs_fr: Optional[float] = None
    score_deal: Optional[int] = None

    # Arbitrage
    alerte_arbitrage: Optional[str] = None
    ecart_arbitrage: Optional[float] = None

    # Lien
    lien_google_shopping: Optional[str] = None

    # Manuel
    prix_achat: Optional[float] = None

    # Meta
    date_scan: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convertit le deal en dictionnaire pour Supabase."""
        return {
            "asin": self.asin,
            "titre": self.titre,
            "categorie": self.categorie,
            "bsr_fr": self.bsr_fr,
            "statut": self.statut,
            "nb_vendeurs_fba": self.nb_vendeurs_fba,
            "amazon_en_stock": self.amazon_en_stock,
            "buy_box_fr": self.buy_box_fr,
            "buy_box_de": self.buy_box_de,
            "buy_box_it": self.buy_box_it,
            "buy_box_es": self.buy_box_es,
            "buy_box_90j_moy_fr": self.buy_box_90j_moy_fr,
            "buy_box_90j_min_fr": self.buy_box_90j_min_fr,
            "referral_fee": self.referral_fee,
            "frais_fba": self.frais_fba,
            "frais_efn": self.frais_efn,
            "envoi_fba": self.envoi_fba,
            "urssaf": self.urssaf,
            "total_frais": self.total_frais,
            "marketplace_recommandee": self.marketplace_recommandee,
            "roi_fr": self.roi_fr,
            "roi_meilleur": self.roi_meilleur,
            "gain_vs_fr": self.gain_vs_fr,
            "score_deal": self.score_deal,
            "alerte_arbitrage": self.alerte_arbitrage,
            "ecart_arbitrage": self.ecart_arbitrage,
            "lien_google_shopping": self.lien_google_shopping,
            "prix_achat": self.prix_achat,
        }
