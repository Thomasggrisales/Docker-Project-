import os
from flask import Flask, render_template, jsonify, request
from flask_pymongo import PyMongo

from dotenv import load_dotenv
from datetime import datetime
from dateutil import parser 
from collections import defaultdict

# Definimos la ruta al archivo .env
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

load_dotenv(dotenv_path)

MONGO_HOST = os.getenv('MONGO_HOST', 'monguito')
MONGO_PORT= os.getenv('MONGO_PORT', '8081') 
MONGO_DB= os.getenv('MONGO_DB', 'proyecto_db') 
MONGO_USER= os.getenv('MONGO_USER', 'admin') 
MONGO_PASSWORD= os.getenv('MONGO_PASSWORD', '1234PA*') 

MONGO_URI = os.getenv('MONGO_URI')


# Get Mongo URI from environment
MONGO_URI = os.getenv('MONGO_URI')

app = Flask(__name__)

# ✅ Correct config key name
app.config["MONGO_URI"] = MONGO_URI


try:
    mongo = PyMongo(app)
    
    sensor1_collection = mongo.db.sensor 
    print("Conexión a MongoDB y colección 'sensor' establecida.")

    sensor1_collection.find_one()
    print("Prueba de lectura a la colección 'sensor' exitosa.")
except Exception as e:
    print(f"Error al conectar o interactuar con MongoDB: {e}")
    mongo = None
    sensor1_collection = None

@app.route('/enviar_dato')
def enviar_dato():
    if sensor1_collection is not None:
        try:
            
            dato_sensor = {"sensor": "temperatura_prueba", "valor": 30.1, "unidad": "C"}
            # Insertamos el dato en la colección 'sensor1'
            result = sensor1_collection.insert_one(dato_sensor)
            return jsonify({
                "mensaje": "Dato de prueba agregado exitosamente a 'sensor'",
                "id": str(result.inserted_id)
            })
        except Exception as e:
            return jsonify({"error": f"Error al insertar en la base de datos: {e}"}), 500
    else:
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 500
    

@app.route('/index')
def index():
    return render_template('index.html')



@app.route('/receive_sensor_data', methods=['POST'])
def receive_sensor_data():
    if sensor1_collection is None:
        
        return jsonify({"error": "La conexión a la base de datos no está establecida."}), 503

    try:
        # Obtener los datos JSON
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No se proporcionó un payload JSON"}), 400

        
        sensor_type = data.get('sensor_type')
        value = data.get('value')
        unit = data.get('unit', 'N/A') 

        if sensor_type is None or value is None:
            return jsonify({"error": "Faltan campos obligatorios: 'sensor_type' o 'value'"}), 400

        
        doc_to_insert = {
            "sensor": sensor_type,
            "valor": value,
            "unidad": unit,
            "timestamp": datetime.now() 
        }

        
        result = sensor1_collection.insert_one(doc_to_insert)


        return jsonify({
            "status": "success",
            "message": "Dato de sensor recibido y guardado exitosamente.",
            "id_mongo": str(result.inserted_id),
            "data_received": doc_to_insert
        }), 201
    except Exception as e:
        print(f"Error al procesar los datos del sensor: {e}")
        return jsonify({"status": "error", "message": f"Error interno del servidor: {e}"}), 500



@app.route('/insert', methods=['GET'])
def insert_data():
    """Inserta un registro de prueba."""
    if sensor1_collection is None:
        return jsonify({"error": "No hay conexión a la base de datos"}), 503

    dato = {
        # Usamos nombres exactos para probar: Temperature y Humidity
        "sensor": "Temperature_Test", 
        "valor": 20.9,
        "unidad": "C",
        "timestamp": datetime.now()
    }
    result = sensor1_collection.insert_one(dato)
    return jsonify({"mensaje": "Dato agregado", "id": str(result.inserted_id)}), 201

# 🔹 1. Endpoint de Estado (/)
@app.route('/', methods=['GET'])
def root_path():
    """Ruta usada por Grafana para probar conexión."""
    return 'OK', 200

# 🔹 2. Endpoint de Búsqueda (/search)
@app.route('/search', methods=['GET', 'POST'])
def search_metrics():
    """Retorna la lista de métricas (valores del campo 'sensor') disponibles."""
    # Los nombres DEBEN COINCIDIR EXACTAMENTE con el valor del campo 'sensor' en tu DB
    metrics = ["Temperature", "Humidity"] 
    return jsonify(metrics)

# 🔹 3. Endpoint de Consulta (/query)
@app.route('/query', methods=['POST'])
def query_data():
    """Consulta MongoDB dentro del rango de tiempo y filtra por el nombre del sensor."""
    if sensor1_collection is None:
        return jsonify({"error": "La conexión a MongoDB no está disponible."}), 503

    req_data = request.get_json(silent=True)
    
    # 1. Verificación de solicitud y extracción de targets/range
    if not req_data or 'range' not in req_data or 'targets' not in req_data:
        return jsonify({"error": "Solicitud JSON inválida o incompleta."}), 400

    try:
        time_from_str = req_data['range']['from']
        time_to_str = req_data['range']['to']
        targets = req_data['targets']
        
        # Parsear las cadenas de tiempo
        time_from = parser.parse(time_from_str)
        time_to = parser.parse(time_to_str)
    except Exception as e:
        # Captura errores si Grafana envía un formato de fecha incorrecto
        print(f"Error al procesar JSON de Grafana (Fechas/Claves): {e}")
        return jsonify({"error": f"Error en el formato de solicitud: {e}"}), 400

    response_data = []

    # 2. Iterar sobre las métricas solicitadas
    for target_info in targets:
        metric_name = target_info['target']
        datapoints = []
        
        # 3. Consulta MongoDB (Filtrando por tiempo Y por el valor del campo 'sensor')
        query_by_metric = {
            'timestamp': {'$gte': time_from, '$lte': time_to},
            'sensor': metric_name 
        }
        
        # Proyección: Solo necesitamos 'valor' y 'timestamp'
        projection_by_metric = {'valor': 1, 'timestamp': 1, '_id': 0}
        
        cursor = sensor1_collection.find(query_by_metric, projection_by_metric).sort("timestamp", 1)

        # 4. Formateo de los datos
        for doc in cursor:
            try:
                # Accede al campo 'valor'
                value = doc.get('valor')
                timestamp_obj = doc.get('timestamp')
                
                # Conversión de tipos y formato
                if value is not None and timestamp_obj:
                    # Convertir el valor a float si es necesario
                    value = float(value) 
                    # Convertir datetime a milisegundos desde la época (EPOCH)
                    timestamp_ms = int(timestamp_obj.timestamp() * 1000)
                    
                    datapoints.append([value, timestamp_ms])
            except Exception as inner_e:
                print(f"⚠️ Documento de DB con error de tipo (valor o timestamp): {inner_e}")
                continue # Saltar este documento y seguir con el siguiente

        # 5. Agregar la serie al JSON de respuesta
        response_data.append({
            "target": metric_name,
            "datapoints": datapoints
        })

    return jsonify(response_data)


# app.py - Nuevo Endpoint

# app.py - Función json_api_data modificada para JSON API
from collections import defaultdict

@app.route('/json_api_data', methods=['POST'])
def json_api_data():
    if sensor1_collection is None:
        return jsonify({"error": "La conexión a MongoDB no está disponible."}), 503

    try:
        cursor = sensor1_collection.find(
            {},
            {"sensor": 1, "valor": 1, "timestamp": 1, "_id": 0}
        ).sort("timestamp", 1)

        grouped_data = defaultdict(list)

        for doc in cursor:
            sensor_type = doc.get("sensor")
            value = doc.get("valor")
            ts = doc.get("timestamp")

            # Validaciones obligatorias
            if sensor_type is None or value is None or ts is None:
                continue

            # Convertir valor a float
            try:
                value = float(value)
            except:
                continue

            # Convertir timestamp Mongo → datetime
            if isinstance(ts, dict) and "$date" in ts:
                ts = datetime.fromtimestamp(int(ts["$date"]["$numberLong"]) / 1000)

            # Convertir a ISO 8601
            time_str = ts.isoformat()

            grouped_data[sensor_type].append({
                "time": time_str,
                "value": value
            })

        return jsonify(grouped_data), 200

    except Exception as e:
        print("ERROR JSON API:", str(e))
        return jsonify({"error": str(e)}), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


