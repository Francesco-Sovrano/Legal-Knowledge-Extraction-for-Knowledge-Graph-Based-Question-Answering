from bottle import run, get, post, route, hook, request, response, static_file
import sys
port = int(sys.argv[1])

###############################################################
# CORS

@route('/<:re:.*>', method='OPTIONS')
def enable_cors_generic_route():
	"""
	This route takes priority over all others. So any request with an OPTIONS
	method will be handled by this function.

	See: https://github.com/bottlepy/bottle/issues/402

	NOTE: This means we won't 404 any invalid path that is an OPTIONS request.
	"""
	add_cors_headers()

@hook('after_request')
def enable_cors_after_request_hook():
	"""
	This executes after every route. We use it to attach CORS headers when
	applicable.
	"""
	add_cors_headers()

def add_cors_headers():
	try:
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
		response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
	except Exception as e:
		print('Error:',e)

###############################################################
# Static Routes

@get("/favicon.ico")
def favicon():
	return static_file("favicon.ico", root="static/img/")

@get("/resources/static/<filepath:re:.*\.css>")
def css(filepath):
	return static_file(filepath, root="static/css/")

@get("/resources/static/<filepath:re:.*\.(eot|otf|svg|ttf|woff|woff2?)>")
def font(filepath):
	return static_file(filepath, root="static/css/")

@get("/resources/static/<filepath:re:.*\.(jpg|png|gif|ico|svg)>")
def img(filepath):
	return static_file(filepath, root="static/img/")

@get("/resources/static/<filepath:re:.*\.js>")
def js(filepath):
	return static_file(filepath, root="static/js/")

@get("/resources/static/<filepath:re:.*\.json>")
def js(filepath):
	return static_file(filepath, root="static/json/")

@get("/documents/<filepath:re:.*\.pdf>")
def docs(filepath):
	return static_file(filepath, root="../oke/documents/")

@get("/<filepath:re:.*\.html>")
def html(filepath):
	print(filepath)
	return static_file(filepath, root="static/html/")

@get("/")
def home():
	return static_file('index.html', root="static/html/")

if __name__ == "__main__":
	run(host='0.0.0.0', port=port, debug=True)
	