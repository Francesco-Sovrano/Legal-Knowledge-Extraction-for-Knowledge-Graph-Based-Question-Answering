const DEBUG = false;
const DBPEDIA_ENDPOINT = "//dbpedia.org/sparql";

const PREFIX_MAP = {
	'my': 'http://my_graph.co/',
	'myfile': 'http://my_graph.co/files/',
	'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
	'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
	'prov': 'http://www.w3.org/ns/prov#',
	'foaf': 'http://xmlns.com/foaf/0.1/',
	'skos': 'http://www.w3.org/2004/02/skos/core#',
	'dct': 'http://purl.org/dc/terms/',
	'dc': 'http://purl.org/dc/terms/',
	'dce': 'http://purl.org/dc/elements/1.1/',
	'owl': 'http://www.w3.org/2002/07/owl#',
	'dbo': 'http://dbpedia.org/ontology/',
	'dbp': 'http://dbpedia.org/property/',
	'dbr': 'http://dbpedia.org/resource/',
	'ns1': 'http://purl.org/linguistics/gold/',
	'vrank': 'http://purl.org/voc/vrank#',
	'wn': 'http://wordnet.princeton.edu/',
	'brusselsreg_en_1215-20212': 'http://my_graph.co/brusselsreg_en_1215-20212/',
	'rome_i_en': 'http://my_graph.co/rome_i_en/',
	'rome_ii_en': 'http://my_graph.co/rome_ii_en/',
}
const PREFIX_MAP_STRING = Object.keys(PREFIX_MAP).map(x => "PREFIX "+x+": <"+PREFIX_MAP[x]+">").join("\n");

function prefixed_string_to_uri(prefixed_string)
{
	prefixed_string = String(prefixed_string);
	if (prefixed_string == '@type')
		return PREFIX_MAP['rdf']+'type';
	var item_list = prefixed_string.split(':');
	if (item_list.length>1 && item_list[0] in PREFIX_MAP)
		return PREFIX_MAP[item_list[0]] + item_list.slice(1).join(':');
	return prefixed_string;
};

function uri_to_prefixed_string(uri)
{
	var prefixed_string = uri;
	for (var [id,url] of Object.entries(PREFIX_MAP).sort((a,b)=>b[0].length-a[0].length))
		prefixed_string = prefixed_string.replace(url,id+':');
	return prefixed_string;
};

const TYPE_URI = prefixed_string_to_uri('rdf:type');
const SUBCLASSOF_URI = prefixed_string_to_uri('rdfs:subClassOf');
const LABEL_URI = prefixed_string_to_uri('rdfs:label');

const HAS_ENTITY_URI = prefixed_string_to_uri('my:hasEntity');
const HAS_SUBCLASS_URI = prefixed_string_to_uri('my:hasSubClass');
const UNKNOWN_TYPE_URI = prefixed_string_to_uri('my:Unknown');
const TYPESET_URI = prefixed_string_to_uri('my:typeSet');
const ENTITY_PERCENTAGE_URI = prefixed_string_to_uri('my:presenceInDataset');
const ENTITY_COUNT_URI = prefixed_string_to_uri('my:entityCount');
const CLASS_COUNT_URI = prefixed_string_to_uri('my:classCount');
const STATEMENT_COUNT_URI = prefixed_string_to_uri('my:statementCount');
const CLASS_LIST_URI = prefixed_string_to_uri('my:hasClass');
const DOCUMENT_TITLE_URI = prefixed_string_to_uri('my:documentTitle');
const DATASET_LIST_URI = prefixed_string_to_uri('my:datasetList');
const PROCESS_LIST_URI = prefixed_string_to_uri('my:processList');
const IS_COMPOSITE_CLASS_BOOL_URI = prefixed_string_to_uri('my:isCompositeClass');
const COMPOSITE_CLASS_SET_URI = prefixed_string_to_uri('my:classSet');
const EP_OVERVIEW_URI = prefixed_string_to_uri('my:explanatoryProcessOverview');
const ANNOTATION_LIST_URI = prefixed_string_to_uri('my:annotationList');
const WORD_ANNOTATION_LIST_URI = prefixed_string_to_uri('my:wordLevelAnnotationList');
const ANNOTATED_SENTENCE_LIST_URI = prefixed_string_to_uri('my:annotatedSentenceList');
const RELATED_TO_URI = prefixed_string_to_uri('my:relatedTo');
const TEXT_URI = prefixed_string_to_uri('my:text');
const PROCESS_INPUT_URI = prefixed_string_to_uri('my:process_input');
const FEATURE_URI = prefixed_string_to_uri('my:feature');
const VALUE_URI = prefixed_string_to_uri('my:value');
const FEATURE_ORDER_URI = prefixed_string_to_uri('my:feature_order');
const COUNTERFACTUAL_API_URI = prefixed_string_to_uri('my:counterfactual_api_url');
const RELEVANT_PROCESS_INPUT_LIST_URI = prefixed_string_to_uri('my:relevant_process_input_list');
const PROPERTY_LIST_URI = prefixed_string_to_uri('my:propertyList');

function build_RDF_item(item, ground=null, source=null) {
	return {
		'@value': prefixed_string_to_uri(item),
		'@ground': ground,
		'@source': source,
	}
}

function isRDFItem(v)
{
	return typeof v==='object' && v!==null && v.constructor.name == "Object" && ('@value' in v);
};

function isArray(v) 
{
	return typeof v==='object' && v!==null && v.constructor.name == "Array";
};

function isDict(v) 
{
	return typeof v==='object' && v!==null && v.constructor.name == "Object" && !isRDFItem(v);
};

function isHTML(str)
{
	var html_pattern = "<(?:\"[^\"]*\"['\"]*|'[^']*'['\"]*|[^'\">])+>";
	var pattern = new RegExp(html_pattern,'i');
	return !!pattern.test(str);
};

function isNumber(str)
{
	return !isNaN(parseInt(str, 10));
}

function isURL(str) 
{
	if (!str)
		return false;
	if (isHTML(str))
		return false;
	if (str.startsWith('../') || str.startsWith('./'))
		return true;
	var url_pattern = '<?(http[s]?:)?//(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+>?';
	var pattern = new RegExp(url_pattern,'i');
	return !!pattern.test(str);
};

function decodeHtmlEntity(encodedString) 
{
	var textArea = document.createElement('textarea');
	textArea.innerHTML = encodedString;
	var object = textArea.value;
	object = String(object).trim()
	object = object.replace(/<|>|"/gi,'')
	return object
}

function pathJoin(parts, sep) 
{
	const separator = sep || '/';
	parts = parts.map((part, index)=>{
		part = String(part);
		 if (index)
			part = part.replace(new RegExp('^' + separator), '');
		 if (index !== parts.length - 1)
			part = part.replace(new RegExp(separator + '$'), '');
		 return part;
	})
	parts = parts.filter(x => x!='');
	return parts.join(separator);
};

function getPath(url)
{
	var reUrlPath = /(?:\w+:)?\/\/[^\/]+(\/.+)*(\/.+)/;
	var urlParts = url.match(reUrlPath) || [url, url];
	path = (urlParts.length > 1) ? urlParts[urlParts.length-1].replace(/\//gi,'') : url;
	if (path.includes('#'))
	{
		splitted_path = path.split('#');
		path = splitted_path[splitted_path.length-1];
	}
	return path;
}

function format_string(v, toLowerCase=true) 
{
	var formatted_string = String(v).replace(/([a-z])([A-Z0-9]+)/g, '$1 $2').replace(/[_ ]+/g, ' ');
	return toLowerCase?formatted_string.toLowerCase():formatted_string;
}

function format_link(link, toLowerCase=true)
{
	return format_string(getPath(link), toLowerCase);
}

function HTMLescape(s) {
    return s.replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
}

function remove_anonymous_entities(data, entity_dict) 
{
	if (isArray(data))
		return data.map(x=>remove_anonymous_entities(x, entity_dict));

	if (isDict(data)) 
	{
		for (var [p,o] of Object.entries(data)) 
		{
			if (p=='@id')
				continue;
			data[p] = remove_anonymous_entities(o, entity_dict);
		}
	}
	else // is RDF item
	{
		var data_desc = get_RDFItem_description(data);
		if (data_desc.startsWith('_:') && data_desc in entity_dict) // anonymous entity
			return entity_dict[data_desc];
	}
	return data;
}

function tuple_list_to_formatted_jsonld(tuple_list)
{
	var jsonld = [];
	for (var [s,p,o] of tuple_list)
	{
		var triple_jsonld = {'@id': s};
		triple_jsonld[p] = o;
		jsonld.push(triple_jsonld);
	}
	// Remove anonymous entities, if possible
	jsonld = format_jsonld(jsonld);
	// return remove_anonymous_entities(
	// 	jsonld,
	// 	get_entity_dict(build_minimal_entity_graph(jsonld))
	// );
	return jsonld;
}

function format_jsonld(jsonld, ground=null, source=null)
{
	if (isArray(jsonld))
		return jsonld.map(x=>format_jsonld(x, ground, source));
	if (!isDict(jsonld))
		return isRDFItem(jsonld)?build_RDF_item(jsonld['@value'], ground, jsonld['@source']):build_RDF_item(jsonld, ground, source)
	// format id
	if ('url' in jsonld && !('@id' in jsonld)) {
		jsonld['@id'] = jsonld['url']
		jsonld['url'] = null
		delete jsonld['url']
	}
	// format predicates
	var new_jsonld = {}
	for (var [predicate, object_list] of Object.entries(jsonld))
	{
		if (isArray(object_list) && object_list.length==0)
			continue
		var uri_predicate = prefixed_string_to_uri(predicate);
		new_jsonld[uri_predicate] = format_jsonld(object_list, ground, source);
	}
	return new_jsonld
}

function replace_jsonld_by_id(jsonld, jsonld_fragment)
{
	if (!('@id' in jsonld_fragment))
		return jsonld;

	if (isArray(jsonld))
		jsonld = jsonld.map(x=>replace_jsonld_by_id(x, jsonld_fragment));
	else if (isDict(jsonld))
	{
		for (var [predicate, object] of Object.entries(jsonld))
			jsonld[predicate] = replace_jsonld_by_id(object, jsonld_fragment);
	}
	else
	{
		if (jsonld['@value'] == jsonld_fragment['@id']['@value'])
			return jsonld_fragment;
	}
	return jsonld;
}

function get_value_in_jsonld_by_key(jsonld, key)
{
	if (isRDFItem(jsonld))
		return [];

	var value_list = [];
	if (isArray(jsonld))
	{
		for (var e of jsonld)
			value_list = value_list.concat(get_value_in_jsonld_by_key(e, key));
	}
	else
	{
		if (key in jsonld)
			return [jsonld[key]];
		if (prefixed_string_to_uri(key) in jsonld)
			return [jsonld[prefixed_string_to_uri(key)]];

		for (var [predicate, object] of Object.entries(jsonld))
			value_list = value_list.concat(get_value_in_jsonld_by_key(object, key));
	}
	return value_list;
}

function zip(arrays) {
    return arrays[0].map(function(_,i){
        return arrays.map(array=>array[i])
    });
}

function download(content, fileName, contentType) {
    var a = document.createElement("a");
    var file = new Blob([content], {type: contentType});
    a.href = URL.createObjectURL(file);
    a.download = fileName;
    a.click();
}

function query_sparql_endpoint(endpoint, queryStr, isDebug=false) 
{
	try {
		var querypart = "query=" + escape(queryStr);
		// Get our HTTP request object.
		var xmlhttp = null;
		if(window.XMLHttpRequest) 
			xmlhttp = new XMLHttpRequest();
	  	else if(window.ActiveXObject) // Code for older versions of IE, like IE6 and before.
			xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
		else 
			alert('Perhaps your browser does not support XMLHttpRequests?');

		// Set up a POST with JSON result format. GET can have caching probs, so POST
		xmlhttp.open('POST', endpoint, false); // `false` makes the request synchronous
		xmlhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
		xmlhttp.setRequestHeader("Accept", "application/sparql-results+json");

		// Send the query to the endpoint.
		xmlhttp.send(querypart);
		if(xmlhttp.readyState == 4) 
		{
			if(isDebug)
				alert("Sparql query error: " + xmlhttp.status + " " + xmlhttp.responseText);
			if(xmlhttp.status == 200) 
				return eval('(' + xmlhttp.responseText + ')');
		}
	}
	catch(e)
	{
		if (DEBUG)
			console.error(e)
	}
	return null
};

function get_array_description(dict_list, limit=null)
{
	return dict_list.slice(0, limit).map(y=>linkify(get_description(y, as_label=false),titlefy(get_known_label(get_description(y, as_label=false))))).join(', ');
}

function get_dict_description(dict, as_label=true)
{
	if (!dict)
		return '';
	var label = '';
	// console.log(dict);
	if (as_label && LABEL_URI in dict && isRDFItem(dict[LABEL_URI]))
		label = dict[LABEL_URI]['@value'];
	else if ('@id' in dict)
		label = dict['@id']['@value'];
	return HTMLescape(String(label).trim());
}

function get_RDFItem_description(item)
{
	if (!item || !('@value' in item))
		return null;
	return HTMLescape(String(item['@value']).trim());
}

function get_description(e, as_label=true, limit=null)
{
	if (isRDFItem(e))
		return get_RDFItem_description(e);
	if (isDict(e))
		return get_dict_description(e, as_label);
	if (isArray(e))
		return get_array_description(e, limit);
	return e;
}

function isInt(value) {
  if (isNaN(value)) {
    return false;
  }
  var x = parseFloat(value);
  return (x | 0) === x;
}

function get_unique_elements(list, id_fn=x=>x) {
  var j = {};

  list.forEach( function(v) {
    j[id_fn(v)] = v;
  });

  return Object.values(j);
}

jQuery.extend(jQuery.expr[':'], {
  shown: function (el, index, selector) {
    return $(el).css('visibility') != 'hidden' && $(el).css('display') != 'none' && !$(el).is(':hidden')
  }
});

INLINE_TAG_LIST = [
	'a',
	'abbr',
	'acronym',
	'annotation',
	'b',
	'bdo',
	'big',
	'br',
	'button',
	'cite',
	'code',
	'dfn',
	'em',
	'i',
	'img',
	'input',
	'kbd',
	'label',
	'map',
	'object',
	'output',
	'q',
	'samp',
	'script',
	'select',
	'small',
	'span',
	'strong',
	'sub',
	'sup',
	'textarea',
	'time',
	'tt',
	'var'
].map(x=>x.toUpperCase());

function htmlDecode(input){
  var e = document.createElement('textarea');
  e.innerHTML = input;
  // handle case of empty input
  return e.childNodes.length === 0 ? "" : e.childNodes[0].nodeValue;
}

function removeAllAttrs(element) {
    for (var i= element.attributes.length; i-->0;)
        element.removeAttributeNode(element.attributes[i]);
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
}

const proximity_chars_regexp = /[^a-zA-Z0-9]/gi;
const tokenise = y=>y.split(proximity_chars_regexp).map(x=>x.toLowerCase())//.filter(x=>x!='');

function annotate_html(html, annotation_list, annotate_fn)
{
	if (!html)
		return html;
	if (!annotation_list)
		return html;
	// console.log(JSON.stringify(annotation_list, null, 4));
	var annotated_html = htmlDecode(html).replace(/ +/g," ").trim(); // get decoded html
	var annotation_list = get_unique_elements(annotation_list, x=>x.text); // remove duplicates
	annotation_list = annotation_list.sort((a,b)=>b.text.length-a.text.length); // descending order
	// var annotation_text_list = annotation_list.map(x=>x.text);
	for (const annotation_dict of annotation_list)
	{
		var sub_text = annotation_dict['text'].trim().replace(/([^a-zA-Z0-9 ]) /gi, '$1');
		// if (annotation_dict['annotation']=='my:risk_performance')
		// {
		// 	console.log(sub_text)
		// }
		var token_list = tokenise(sub_text);
		
		const cleaned_sub_text = token_list.join(' ');
		const regexp = new RegExp(escapeRegExp(cleaned_sub_text).trim(), 'gi')
		if (tokenise(annotated_html).join(' ').search(regexp)<0)
			continue;

		const annotation_uri = annotation_dict['annotation'];
		const last_token = token_list[token_list.length-1];
		var start_idx = annotated_html.length;
		while (start_idx >= 0)
		{
			var splitted_html = annotated_html.slice(0,start_idx).split('>');
			var added = false;
			for (var i=splitted_html.length-1; !added && i>=0; --i)
			{
				start_idx -= splitted_html[i].length+1;
				var content = splitted_html[i].split('<')[0];
				if (tokenise(content).join(' ').search(regexp)<0)
					continue;

				var splitted_content = tokenise(content);
				var e = splitted_content.length;
				for (var s=splitted_content.length-1; !added && s>=0; --s)
				{
					if (splitted_content[s] == last_token)
						e = s+1;
					var more_precise_content_idx = 0;
					var found = false;
					for (var idx=s; !found && idx<e; idx++)
					{
						if (splitted_content.slice(idx,idx+token_list.length).join(' ') == cleaned_sub_text)
							found = true;
						else
							more_precise_content_idx += splitted_content[idx].length+1
					}
					if (found)
					{
						const start = start_idx + 1 + more_precise_content_idx + s + splitted_content.slice(0,s).map(x=>x.length).reduce((a,b)=>a+b, 0);
						const end = start+splitted_content.slice(s,e).map(x=>x.length).reduce((a,b)=>a+b, 0)+(e-s-1); // start+splitted_content.slice(s,e).join(' ').length;
						// e = s;
						added = true;
						start_idx = start;
						
						// keep the longest annotation, avoid nesting
						const initial_part = annotated_html.slice(0,start);
						const opening_annotation_tags = [...initial_part.matchAll(new RegExp('<annotation', 'gi'))];
						const closing_annotation_tags = [...initial_part.matchAll(new RegExp('</annotation>', 'gi'))];
						if (opening_annotation_tags.length == closing_annotation_tags.length)
						{
							const middle_part = annotated_html.slice(start,end);
							const final_part = annotated_html.slice(end);
							annotated_html = initial_part+`<annotation>${annotate_fn(annotation_uri,middle_part)}</annotation>`+final_part;
						}
					}
				}
			}
		}
		// console.log(start_idx,annotated_html.length);
	}
	return annotated_html;
}

function get_annotation_list_from_formatted_jsonld(jsonld)
{
	var sentenceListList = get_value_in_jsonld_by_key(jsonld, 'my:sentenceList');
	if (sentenceListList.length < 1)
		return [];
	var annotation_list = [];
	for (var sentenceList of sentenceListList)
	{
		for (var sentence of sentenceList)
		{
			if (ANNOTATION_LIST_URI in sentence)
			{
				annotation_list.push({
					'text': get_RDFItem_description(sentence[TEXT_URI]),
					'annotation': get_RDFItem_description(sentence[ANNOTATION_LIST_URI][0][RELATED_TO_URI]),
				});
			}
			if (WORD_ANNOTATION_LIST_URI in sentence)
			{
				for (var word_annotation of sentence[WORD_ANNOTATION_LIST_URI])
				{
					annotation_list.push({
						'text': get_RDFItem_description(word_annotation[TEXT_URI]),
						'annotation': get_RDFItem_description(word_annotation[ANNOTATION_LIST_URI][0][RELATED_TO_URI]),
					});
				}
			}
		}
	}
	return annotation_list
}

function get_process_input_dict_from_formatted_jsonld(jsonld)
{
	var process_list = get_unique_elements([].concat(...get_value_in_jsonld_by_key(jsonld, 'my:processList')), x=>get_dict_description(x));
	var process_input_dict = {};
	for (var p of process_list)
	{
		var process_input = p[PROCESS_INPUT_URI];
		var process_input_list = []
		for (var pi of process_input)
		{
			var input_dict = {}
			for (var k of ['@id', VALUE_URI, FEATURE_ORDER_URI, COUNTERFACTUAL_API_URI])
				input_dict[k] = get_RDFItem_description(pi[k]);
			process_input_list.push(input_dict);
		}
		process_input_dict[get_dict_description(p)] = process_input_list;
	}
	return process_input_dict;
}

function get_DOM_element_distance(element1,element2)
{
	var o1 = $(element1).offset();
	var o2 = $(element2).offset();
	var dx = o1.left - o2.left;
	var dy = o1.top - o2.top;
	return Math.sqrt(dx * dx + dy * dy);
}

function query_wikipedia_by_title(title, callback_fn)
{
	console.log(`Expanding ${title} on Wikipedia.`);
	try {
		$.ajax({
			url: "//en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exintro&explaintext&redirects=1&titles="+title, 
			method: 'GET',
			crossDomain: true,
			dataType: 'jsonp',
			success: function(data) {
				if (data.query && data.query.pages) 
				{
					for (var i in data.query.pages) 
					{
						var response = {
							'@id': title,
							'rdfs:label': data.query.pages[i].title,
							'dbo:abstract': data.query.pages[i].extract
						};
					}
					callback_fn(response);
				}
			},
		});
	} catch(e) {
		if (DEBUG)
			console.error(e);
	}
}

function titlefy(s) {
	if (!s)
		return s;
	return s[0].toUpperCase() + s.slice(1);
}

function get(dict, key, def=null)
{
	var v = dict[key];
	return v?v:def;
}

function format_percentage(v, decimals=2)
{
	return (v*100).toFixed(decimals).toString().replace('.'+'0'.repeat(decimals),'')+'%';
}

function clip(n, min,max)
{
	if (n < min)
		return min;
	else if (n > max)
		return max;
	return n;
}
