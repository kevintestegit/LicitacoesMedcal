import json
from modules.database.database import get_session, Configuracao

class EligibilityChecker:
    def __init__(self):
        self.session = get_session()

    def get_company_profile(self):
        """Retrieves company profile from DB."""
        config = self.session.query(Configuracao).filter_by(chave='company_profile').first()
        if config:
            return json.loads(config.valor)
        return {}

    def save_company_profile(self, profile_data: dict):
        """Saves company profile to DB."""
        config = self.session.query(Configuracao).filter_by(chave='company_profile').first()
        if not config:
            config = Configuracao(chave='company_profile', valor=json.dumps(profile_data))
            self.session.add(config)
        else:
            config.valor = json.dumps(profile_data)
        self.session.commit()

    def check_eligibility(self, licitacao_data: dict, ai_analysis: dict = None) -> dict:
        """
        Checks if the company is eligible for the bidding.
        Returns a dict with 'eligible' (bool) and 'reasons' (list).
        """
        profile = self.get_company_profile()
        if not profile:
            return {"eligible": True, "warnings": ["Perfil da empresa não configurado. Verificação ignorada."]}

        reasons = []
        warnings = []
        eligible = True

        # 1. Geographic Check
        operating_states = profile.get('estados_atuacao', [])
        if operating_states and licitacao_data.get('uf') not in operating_states:
            eligible = False
            reasons.append(f"Empresa não atua no estado {licitacao_data.get('uf')}")

        # 2. Modalidade Check (Example: maybe we don't do 'Concorrência')
        # (Not implemented yet, depends on user pref)

        # 3. AI Analysis Check (if available)
        if ai_analysis:
            # Check for specific red flags identified by AI
            red_flags = ai_analysis.get('red_flags', [])
            for flag in red_flags:
                warnings.append(f"IA Alertou: {flag}")

        return {
            "eligible": eligible,
            "reasons": reasons,
            "warnings": warnings
        }
