#!venv/bin/python
from app import webapp
# run local ONLY to avoid potential incoming traffic on my own machine
#webapp.run(host='0.0.0.0',port=80, debug=True)
webapp.run(host='localhost',port=5000, debug=True)
#webapp.run(host='0.0.0.0')
