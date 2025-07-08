from flask import Flask, request, jsonify
import logging
from datetime import datetime, timedelta
import requests
import re

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HotelBookingSystem:
    def __init__(self):
        self.base_url = "http://200.148.248.210:8366/datasnap/rest/v1"
        self.client_id = "2B038F97E8E8A3DB89CB40A76210C0B4"
        self.client_secret = "DE4A2599287851214AE09156276886C8"
        self._cache_token = None
        self._token_expiry = None

    def obter_token(self):
        """Obtém token de acesso com cache"""
        if self._cache_token and self._token_expiry and datetime.now() < self._token_expiry:
            logger.info("Usando token em cache")
            return self._cache_token
        
        try:
            url = f"{self.base_url}/liberar?client_id={self.client_id}&client_secret={self.client_secret}"
            logger.info(f"Solicitando novo token: {url}")
            
            response = requests.post(url, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            logger.info(f"Token obtido: {token_data}")
            
            self._cache_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 30)
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 5)
            
            return self._cache_token
            
        except Exception as e:
            logger.error(f"Erro ao obter token: {e}")
            raise

    def consultar_disponibilidade(self, token, data_checkin, data_checkout):
        """Consulta disponibilidade na API"""
        try:
            url = f"{self.base_url}/Disponibilidade?dataInicial={data_checkin}&dataFinal={data_checkout}"
            headers = {"Authorization": f"Bearer {token}"}
            
            logger.info(f"Consultando disponibilidade: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Dados de disponibilidade recebidos: {len(data.get('listaTipoApto', []))} tipos")
            
            return data
            
        except Exception as e:
            logger.error(f"Erro ao consultar disponibilidade: {e}")
            raise

    def obter_capacidade(self, codigo, nome):
        """Determina capacidade do quarto baseado no código e nome"""
        if not codigo:
            codigo = ""
        
        codigo = str(codigo).upper()
        nome_upper = str(nome).upper() if nome else ""
        
        # Lógica melhorada para determinar capacidade
        if "5" in codigo or "QUINT" in nome_upper:
            return 5
        elif "4" in codigo or "Q" in codigo or "QUAD" in nome_upper:
            return 4
        elif "3" in codigo or "TRIP" in nome_upper:
            return 3
        elif "2" in codigo or "DUPLO" in nome_upper or "DOUBLE" in nome_upper:
            return 2
        elif "1" in codigo or "SINGLE" in nome_upper or "SOLT" in nome_upper:
            return 1
        
        # Padrão para apartamentos sem identificação clara
        return 2

    def verificar_disponibilidade_periodo(self, tipo, data_checkin, data_checkout):
        """Verifica se há disponibilidade em todo o período"""
        situacoes = tipo.get("listaSituacaoTipoApto", [])
        
        if not situacoes:
            logger.warning(f"Nenhuma situação encontrada para tipo: {tipo.get('nome')}")
            return False, "Sem dados de situação"
        
        try:
            data_inicio = datetime.strptime(data_checkin, "%Y-%m-%d")
            data_fim = datetime.strptime(data_checkout, "%Y-%m-%d")
            
            logger.info(f"Verificando disponibilidade de {data_inicio.date()} a {data_fim.date()}")
            
            dias_sem_disponibilidade = []
            
            for dia in situacoes:
                try:
                    data_dia = datetime.strptime(dia["data"], "%Y-%m-%d")
                    
                    # Verifica se o dia está no período (checkout não incluso)
                    if data_inicio <= data_dia < data_fim:
                        disponivel = dia.get("qtdeDisponivel", 0)
                        manutencao = dia.get("qtdeManutencao", 0)
                        quartos_disponiveis = disponivel - manutencao
                        
                        logger.info(f"Dia {dia['data']}: disponível={disponivel}, manutenção={manutencao}, resultado={quartos_disponiveis}")
                        
                        if quartos_disponiveis <= 0:
                            dias_sem_disponibilidade.append(dia["data"])
                            
                except ValueError as e:
                    logger.error(f"Erro ao processar data {dia.get('data')}: {e}")
                    continue
            
            if dias_sem_disponibilidade:
                return False, dias_sem_disponibilidade[0]
            
            return True, None
            
        except Exception as e:
            logger.error(f"Erro ao verificar disponibilidade: {e}")
            return False, str(e)

    def filtrar_por_capacidade(self, tipos_disponiveis, pessoas_que_precisam_cama):
        """Filtra tipos de apartamento por capacidade"""
        tipos_adequados = []
        
        for tipo in tipos_disponiveis:
            nome = tipo.get("nome", "")
            codigo = tipo.get("codigo", "")
            capacidade = self.obter_capacidade(codigo, nome)
            
            if capacidade >= pessoas_que_precisam_cama:
                tipos_adequados.append({
                    "nome": nome,
                    "codigo": codigo,
                    "capacidade": capacidade
                })
        
        return tipos_adequados

# Criando o sistema
sistema = HotelBookingSystem()

@app.route("/consulta", methods=["POST"])
def consulta():
    try:
        dados = request.json
        logger.info(f"Dados recebidos: {dados}")
        
        # Validação de entrada
        data_checkin = dados.get("data_checkin")
        data_checkout = dados.get("data_checkout")
        adultos = dados.get("adultos")
        criancas_ate_5 = dados.get("criancas_ate_5")
        criancas_6_mais = dados.get("criancas_6_mais")

        if not all([data_checkin, data_checkout, 
                   adultos is not None, 
                   criancas_ate_5 is not None, 
                   criancas_6_mais is not None]):
            return jsonify({"erro": "Parâmetros obrigatórios: data_checkin, data_checkout, adultos, criancas_ate_5, criancas_6_mais"}), 400

        # Validação de datas
        try:
            checkin_date = datetime.strptime(data_checkin, "%Y-%m-%d")
            checkout_date = datetime.strptime(data_checkout, "%Y-%m-%d")
            
            if checkin_date >= checkout_date:
                return jsonify({"erro": "Data de checkout deve ser posterior à data de checkin"}), 400
                
        except ValueError:
            return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD"}), 400

        # Cálculo de pessoas que precisam de cama
        pessoas_que_precisam_cama = adultos + criancas_6_mais
        
        logger.info(f"Busca: {data_checkin} a {data_checkout}, {pessoas_que_precisam_cama} pessoas precisam de cama")

        # Consulta à API
        token = sistema.obter_token()
        dados_disponibilidade = sistema.consultar_disponibilidade(token, data_checkin, data_checkout)

        lista_tipos = dados_disponibilidade.get("listaTipoApto", [])
        logger.info(f"Tipos recebidos da API: {len(lista_tipos)}")

        # Filtragem por disponibilidade
        tipos_disponiveis = []
        tipos_indisponiveis = []

        for tipo in lista_tipos:
            nome = tipo.get("nome", "")
            codigo = tipo.get("codigo", "")
            
            disponivel, motivo = sistema.verificar_disponibilidade_periodo(tipo, data_checkin, data_checkout)
            
            if disponivel:
                tipos_disponiveis.append(tipo)
            else:
                tipos_indisponiveis.append({
                    "nome": nome,
                    "codigo": codigo,
                    "motivo": motivo
                })

        # Filtragem por capacidade
        tipos_adequados = sistema.filtrar_por_capacidade(tipos_disponiveis, pessoas_que_precisam_cama)

        # Resultado final
        resultado = {
            "parametros": {
                "data_checkin": data_checkin,
                "data_checkout": data_checkout,
                "adultos": adultos,
                "criancas_ate_5": criancas_ate_5,
                "criancas_6_mais": criancas_6_mais,
                "pessoas_que_precisam_cama": pessoas_que_precisam_cama
            },
            "resumo": {
                "total_tipos": len(lista_tipos),
                "tipos_disponiveis": len(tipos_disponiveis),
                "tipos_adequados": len(tipos_adequados)
            },
            "apartamentos_disponiveis": tipos_adequados,
            "apartamentos_indisponiveis": tipos_indisponiveis
        }

        logger.info(f"Resultado: {len(tipos_adequados)} apartamentos adequados encontrados")
        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Erro na API: {e}")
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health():
    """Endpoint de verificação de saúde"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
