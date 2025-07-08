from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/consulta', methods=['POST'])
def consulta():
    data = request.json
    nome = data.get('nome')

    # Simulação de chamada externa e retorno
    resultado = {
        "mensagem": f"Olá, {nome}. Consulta feita com sucesso!"
    }

    return jsonify(resultado)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
