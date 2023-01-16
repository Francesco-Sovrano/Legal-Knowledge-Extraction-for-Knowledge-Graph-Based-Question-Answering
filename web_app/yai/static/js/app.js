const OKE_SERVER_URL = location.protocol+'//'+location.hostname+(location.port ? ':'+(parseInt(location.port,10)+2): '')+'/';
console.log('OKE_SERVER_URL:', OKE_SERVER_URL);
const GET_OVERVIEW_API = OKE_SERVER_URL+"overview";
const GET_ANSWER_API = OKE_SERVER_URL+"answer";
const GET_ANNOTATION_API = OKE_SERVER_URL+"annotation";

var app = new Vue({
	el: '#app',
	data: {
		answer_list: [],
		empty_answers: true,
		loading_answers: false,
		question_text: '',
		important_answer_list: [],
		summary_answer: '',
		show_details: false,
		single_answer_details: [],
		documents: {
			'myfile:BrusselsReg_EN_1215-20212': {
				url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32012R1215&from=EN', // 'documents/BrusselsReg_EN_1215-20212.pdf',
				name: 'Brussels I bis Regulation EU 1215/2012',
			},
			'myfile:Rome_I_EN': {
				url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32008R0593&from=EN', // 'documents/Rome I_EN.pdf',
				name: 'Rome I Regulation EC 593/2008',
			},
			'myfile:Rome_II_EN': {
				url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32007R0864&from=EN', // 'documents/Rome II_EN.pdf',
				name: 'Rome II Regulation EC 864/2007',
			}
		}
	},
	methods: {
		question: function(event) {
			// console.log(event);
			var self = this;
			self.loading_answers = true;
			self.answer_list = [];
			self.show_details = false;

			var x = event.target.value.replace(/(\r\n|\n|\r)/gm, "").trim();
			x = x.charAt(0).toUpperCase() + x.slice(1);
			console.log('Sending question:',x);
			$.ajax({
				type: "GET",
				url: GET_ANSWER_API,
				responseType:'application/json',
				data: {
					'question': x, 
					// 'summarised': true
				},
				success: function (result) {
					// console.log('Getting answer:',JSON.stringify(result));
					self.loading_answers = false;
					if (!result)
					{
						self.empty_answers = true;
						return;
					}
					var question = Object.keys(result)[0];
					var important_answer_list = result[question];
					self.empty_answers = false;
					self.question_text = question;
					self.important_answer_list = [];
					self.single_answer_details = [];
					// console.log('Getting answer:',JSON.stringify(important_answer_list));
					console.log('Getting answer..');
					for (var answer of important_answer_list) {
						answer.confidence = (answer.confidence*100).toFixed(2).toString()+'%';
						if (answer.annotation)
						{
							var jsonld = build_minimal_entity_graph(tuple_list_to_formatted_jsonld(answer.annotation));
							KNOWN_ENTITY_DICT = get_entity_dict(jsonld);
							var source_dict = jsonld[0]; // the biggest
							var doc_id = get_description(source_dict[prefixed_string_to_uri('my:docID')]);
							if (!doc_id)
							{
								answer.document = '';
								continue;
							}
							answer.document = self.documents[uri_to_prefixed_string(doc_id)];

							var article_id = get_description(source_dict[prefixed_string_to_uri('my:article_id')]);
							if (article_id)
							{
								var article = [article_id];
								var paragraph_id = get_description(source_dict[prefixed_string_to_uri('my:paragraph_id')]);
								if (paragraph_id)
									article.push(paragraph_id);
								answer.article = article.map(get_known_label).join('.');
							}
						}
						else 
						{
							answer.document = '';
							continue;
						}
						self.important_answer_list.push(answer);
					}
					if (self.important_answer_list.length == 0)
						self.empty_answers = true;
				},
			});
		}
	}
})
