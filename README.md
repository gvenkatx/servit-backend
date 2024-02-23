Steps to compile and run timefold server

1. mvn install -Dquarkus.http.port=<timefold port> -Dquarkus.http.host=<timefold host>
2. java -jar target/quarkus-app/quarkus-run.jar &


Steps to run Python code

1. Clone Git repo: git clone https://github.com/gvenkatx/servit-backend.git
2. Copy the following 2 files to the servit-backend/ directory: serviceAccountKey.json and routeplanParams.json
3. Install Python 3.11 if needed: sudo dnf install python3.11
4. Create virtual environment: python3.11 -m venv <virtual env name>
5. Activate virtual environment: source <virtual env name>/bin/activate
6. cd servit-backend
7. pip3 install -r ./requirements.txt
8. Start serving python flask app:  gunicorn -b 0.0.0.0:<port> create_routeplan:app
9. Invoke creation of route plan:  curl -X GET http://<timefold host>:<port>
