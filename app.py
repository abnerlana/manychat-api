from flask import Flask, request, jsonify
from datetime import datetime
import logging

app = Flask(__name__)

# Importa sua classe do arquivo onde está definida
# Aqui assumo que sua classe HotelBookingSystem está em hotel_booking.py, adapte conforme seu arquivo
from hotel_booking import HotelBookingSystem

sistema = HotelBookingSystem()

@app.route("/consulta", methods=["POST"])
def consulta():
    try:
        dados = request.json

        data_checkin = dados.get("data_checkin")
        data_checkout = dados.get("data_checkout")
        adultos = dados.get("adultos")
        criancas_ate_5 = dados.get("criancas_ate_5")
        criancas_6_mais = dados.get("criancas_6_mais")

        if not (data_checkin and data_checkout and adultos is not None and criancas_ate_5 is not None and criancas_6_mais is not None):
            return jsonify({"erro": "Parâmetros insuficientes"}), 400

        data_checkin_obj = datetime.strptime(data_checkin, "%Y-%m-%d")
        data_checkout_obj = datetime.strptime(data_checkout, "%Y-%m-%d")

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
        logging.error(f"Erro na API /consulta: {e}")
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
