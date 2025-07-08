from flask import Flask, request, jsonify
import logging
from datetime import datetime, timedelta
import requests
import re

app = Flask(__name__)

# --- Aqui começa sua classe HotelBookingSystem (simplificada pra ficar dentro do app.py) ---
class HotelBookingSystem:
    def __init__(self):
        self.base_url = "http://200.148.248.210:8366/datasnap/rest/v1"
        self.client_id = "2B038F97E8E8A3DB89CB40A76210C0B4"
        self.client_secret = "DE4A2599287851214AE09156276886C8"
        self._cache_token = None
        self._token_expiry = None

    def obter_token(self):
        if self._cache_token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._cache_token
        url = f"{self.base_url}/liberar?client_id={self.client_id}&client_secret={self.client_secret}"
        response = requests.post(url)
        response.raise_for_status()
        token_data = response.json()
        self._cache_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 30)
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 5)
        return self._cache_token

    def consultar_disponibilidade(self, token, data_checkin, data_checkout):
        url = f"{self.base_url}/Disponibilidade?dataInicial={data_checkin}&dataFinal={data_checkout}"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def obter_capacidade(self, codigo, nome):
        codigo = codigo.upper()
        if "3" in codigo:
            return 3
        elif "4" in codigo or "Q" in codigo:
            return 4
        elif "5" in codigo:
            return 5
        return 2  # padrão

    def verificar_disponibilidade_periodo(self, tipo, data_checkin, data_checkout):
        situacoes = tipo.get("listaSituacaoTipoApto", [])
        data_inicio = datetime.strptime(data_checkin, "%Y-%m-%d")
        data_fim = datetime.strptime(data_checkout, "%Y-%m-%d")
        for dia in situacoes:
            data_dia = datetime.strptime(dia["data"], "%Y-%m-%d")
            if data_inicio <= data_dia < data_fim:
                disponivel = dia.get("qtdeDisponivel", 0)
                manutencao = dia.get("qtdeManutencao", 0)
                quartos_disponiveis = disponivel - manutencao
                if quartos_disponiveis <= 0:
                    return False, dia["data"]
        return True, None

# Criando o sistema
sistema = HotelBookingSystem()

# --- Aqui a parte do Flask que recebe dados e responde ---
@app.route("/consulta", methods=["POST"])
def consulta():
    try:
        dados = request.json
        data_checkin = dados.get("data_checkin")  # formato: "2025-07-15"
        data_checkout = dados.get("data_checkout")
        adultos = dados.get("adultos")
        criancas_ate_5 = dados.get("criancas_ate_5")
        criancas_6_mais = dados.get("criancas_6_mais")

        if not (data_checkin and data_checkout and adultos is not None and criancas_ate_5 is not None and criancas_6_mais is not None):
            return jsonify({"erro": "Faltam parâmetros"}), 400

        pessoas_que_precisam_cama = adultos + criancas_6_mais

        token = sistema.obter_token()
        dados_disponibilidade = sistema.consultar_disponibilidade(token, data_checkin, data_checkout)

        lista_tipos = dados_disponibilidade.get("listaTipoApto", [])
        disponiveis = []

        for tipo in lista_tipos:
            nome = tipo.get("nome")
            codigo = tipo.get("codigo")
            capacidade = sistema.obter_capacidade(codigo, nome)
            disponivel, _ = sistema.verificar_disponibilidade_periodo(tipo, data_checkin, data_checkout)
            if disponivel and capacidade >= pessoas_que_precisam_cama:
                disponiveis.append({"nome": nome, "codigo": codigo, "capacidade": capacidade})

        return jsonify({"disponiveis": disponiveis})

    except Exception as e:
        logging.error(f"Erro na API: {e}")
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
