OVERVIEW_CACHE = {};
TAXONOMICAL_VIEW_CACHE = {};
ANNOTATION_CACHE = {};
ANNOTATED_HTML_CACHE = {};
KNOWN_KNOWLEDGE_GRAPH = [];

Vue.component("template_tree", {
	template: `
		<div>
			<div>
				<span v-html="annotatedText"></span>
				<span v-if="isParent" class="detail_btn" @click="toggle">[{{ isOpen ? 'Less..' : 'More..' }}]</span>
			</div>
			<ul v-if="isOpen && isParent">
				<li v-for="(child, index) in item.children">
					<template_tree :key="index" :item="child" :annotation_list="annotation_list"></template_tree>
				</li>
			</ul>
		</div>
	`,
	props: {
		item: Object,
		annotation_list: Array,
	},
	data: function() {
		return {
			isOpen: this.item.expanded
		};
	},
	computed: {
		isParent: function() {
			return this.item.children && this.item.children.length;
		},
		annotatedText: function() {
			var txt = this.item.text;
			if (txt in ANNOTATED_HTML_CACHE)
				return ANNOTATED_HTML_CACHE[txt];
			// console.log('Annotating with:', this.annotation_list);
			return ANNOTATED_HTML_CACHE[txt] = annotate_html(txt, this.annotation_list, linkify);
		},
	},
	methods: {
		toggle: function() {
			this.isOpen = !this.isOpen;
		},
	}
});

Vue.component("overview", {
	template: `
		<b-tab :active="active_fn()">
			<template v-slot:title>
				<b-spinner type="border" small v-if="loading"></b-spinner> {{label}}
			</template>
			<div>
				<b-button-close @click="close_fn()">
			</div>
			<div>
				<h1>{{ label }}</h1>
				<div class="d-block">
					<p v-if="loading">Loading overview, please wait a while..</p>
					<p v-if="empty">No overview available.</p>
					<b-alert variant="danger" dismissible fade :show="show_error_alert" @dismissed="show_error_alert=false">
						{{error_message}}
					</b-alert>
					<div v-if="!loading && !empty">
						<div v-if="taxonomical_view.length>0">
							<ul>
								<li v-for="view in taxonomical_view">
									<template_tree :item="view" :annotation_list="annotation_list"></template_tree>
								</li>
							</ul>						
						</div>
						<div v-for="(overview_tree,question) in question_overview_tree" v-if="overview_tree!=null">
							<b>{{question?question:'Extra'}}</b>
							<ul>
								<li v-for="overview in overview_tree">
									<template_tree :item="overview" :annotation_list="annotation_list"></template_tree>
								</li>
							</ul>						
						</div>
					</div>
				</div>
			</div>
		</b-tab>
	`,
	props: {
		uri: String,
		label: String,
		active_fn: {
			type: Function,
			default: function () {}
		},
		close_fn: {
			type: Function,
			default: function () {}
		},
		onload_fn: {
			type: Function,
			default: function () {}
		},
	},
	data: function() {
		return {
			loading: true,
			empty: false,
			show_error_alert: false,
			error_message: '',

			question_overview_tree: {},
			taxonomical_view: [],
			annotation_list: [],
		};
	},
	// methods: {
	// 	format_label: function(label) {
	// 		return tokenise(label).filter(x=>x!='').join(' ');
	// 	}
	// },
	created: function() {
		var self = this;
		// self.uri = self.uri.toLowerCase();
		if (self.uri in OVERVIEW_CACHE)
		{
			self.question_overview_tree = OVERVIEW_CACHE[self.uri]
			self.taxonomical_view = TAXONOMICAL_VIEW_CACHE[self.uri];
			self.annotation_list = ANNOTATION_CACHE[self.uri];
			self.loading = false;
			if (!self.question_overview_tree)
				self.empty = true;
			return;
		}
		console.log('Shifting towards topic:', self.uri, self.label);
		self.loading = true;
		$.ajax({
			type: "GET",
			url: GET_OVERVIEW_API,
			responseType:'application/json',
			data: {
				'concept_uri': self.uri, 
			},
			success: function (result) {
				console.log('Processing overview', result);
				self.show_error_alert = false;
				self.loading = false;
				self.onload_fn();
				// Check cache
				if (!result)
				{
					self.empty = true;
					OVERVIEW_CACHE[self.uri] = null;
					ANNOTATION_CACHE[self.uri] = null;
					TAXONOMICAL_VIEW_CACHE[self.uri] = null;
					return;
				}
				self.empty = false;
				// Setup KNOWN_ENTITY_DICT
				var taxonomical_view = tuple_list_to_formatted_jsonld(result.taxonomical_view);
				// Update the known entity dict (cache)
				KNOWN_KNOWLEDGE_GRAPH = KNOWN_KNOWLEDGE_GRAPH.concat(taxonomical_view);
				KNOWN_ENTITY_DICT = get_typed_entity_dict_from_jsonld(KNOWN_KNOWLEDGE_GRAPH);
				// Setup and annotate question summary tree
				var annotation_list = result.annotation_list;
				// IMPORTANT: filter out all the annotations referring to the exact concept in overview.
				// annotation_list = annotation_list.filter(x => x.annotation != self.uri);
				// Populate the question_overview_tree
				var question_summary_tree = result.question_summary_tree;
				if (question_summary_tree)
				{
					for (var [question,summary_tree] of Object.entries(question_summary_tree))
					{
						if (!summary_tree.summary)
							continue;
						summary_tree = summary_tree_to_jsonld(summary_tree);
						summary_tree = format_jsonld(summary_tree);
						summary_tree = jsonld_to_nestedlist(summary_tree);
						self.question_overview_tree[question] = summary_tree;
					}
				}
				// Set taxonomical_view
				const prefixed_string = prefixed_string_to_uri(self.uri);
				self.taxonomical_view = jsonld_to_nestedlist(nest_jsonld(KNOWN_ENTITY_DICT[prefixed_string], KNOWN_ENTITY_DICT, [prefixed_string], 2));
				self.annotation_list = annotation_list;
				// Cache question summary tree
				OVERVIEW_CACHE[self.uri] = self.question_overview_tree;
				ANNOTATION_CACHE[self.uri] = self.annotation_list;
				TAXONOMICAL_VIEW_CACHE[self.uri] = self.taxonomical_view;
			},
			error: function(result) {
				const prefixed_string = prefixed_string_to_uri(self.uri);
				self.loading = false;
				if (self.uri in ANNOTATION_CACHE)
				{
					self.taxonomical_view = TAXONOMICAL_VIEW_CACHE[self.uri];
					self.annotation_list = ANNOTATION_CACHE[self.uri];
				}
				else 
				{
					self.error_message = result;
					self.show_error_alert = true;
					// expand_link(
					// 	prefixed_string_to_uri(self.uri), 
					// 	x=>{
					// 		console.log(x);
					// 	}, 
					// 	KNOWN_ENTITY_DICT
					// );
				}
			},
		});
	},
});

Vue.component("answer", {
	template: `
		<div>
			<input 
				placeholder="Write a question.. e.g. Which law is applicable to a non-contractual obligation?" 
				value="Which law is applicable to a non-contractual obligation?" 
				type="text" 
				class="form-control input-lg" 
				aria-label="Write a question.. e.g. Which law is applicable to a non-contractual obligation?" 
				aria-describedby="inputGroup-sizing-sm" 
				v-on:keydown.enter="ask"
			>
			<hr>
			<p v-if="loading_answers">Loading answers, please wait a while..</p>
			<p v-if="empty_answers">No answers found.</p>
			<b-alert variant="danger" dismissible fade :show="show_error_alert" @dismissed="show_error_alert=false">
				{{error_message}}
			</b-alert>
			<b-alert variant="warning" dismissible fade :show="show_warning_alert" @dismissed="show_warning_alert=false">
				{{warning_message}}
			</b-alert>
			<div v-if="!loading_answers && !empty_answers && answer_tree">
				<p>
					<strong>Question</strong>: {{ question_text }}
				</p>
				<div>
					<strong>Answer</strong>:
					<ul>
						<li v-for="answer in answer_tree">
							<template_tree :item="answer" :annotation_list="answer_annotation_list"></template_tree>
						</li>
						<li v-for="quality in answer_quality">
							<template_tree :item="quality" :annotation_list="[]"></template_tree>							
						</li>
					</ul>
				</div>
			</div>
		</div>
	`,
	data: function() {
		return {
			show_error_alert: false,
			error_message: '',

			show_warning_alert: false,
			warning_message: '',

			empty_answers: false,
			loading_answers: false,
			question_text: '',
			answer_tree: null,
			answer_annotation_list: [],
			answer_quality: null,
		};
	},
	methods: {
		ask: function(event) {
			// console.log(event);
			var self = this;
			self.loading_answers = true;
			self.empty_answers = false;
			self.show_warning_alert = false;
			self.show_error_alert = false;

			var x = titlefy(event.target.value.replace(/(\r\n|\n|\r)/gm, "").trim());
			console.log('Sending question:',x);
			$.ajax({
				type: "GET",
				url: GET_ANSWER_API,
				responseType:'application/json',
				data: {'question': x},
				success: function (result) {
					console.log('Processing answer');
					// console.log('Getting answer:',JSON.stringify(result));
					self.loading_answers = false;
					if (!result)
					{
						self.empty_answers = true;
						return;
					}
					const annotation_list = result.annotation_list;
					var question_summary_tree = result.question_summary_tree;
					const question = Object.keys(question_summary_tree)[0];
					var summary_tree = summary_tree_to_jsonld(question_summary_tree[question]);
					const answer_quality = result.quality[question];

					self.show_error_alert = false;
					self.empty_answers = false;
					self.question_text = question;
					self.answer_tree = jsonld_to_nestedlist(format_jsonld(summary_tree));
					self.answer_annotation_list = annotation_list;
					self.answer_quality = jsonld_to_nestedlist(format_jsonld({'my:answer_quality': pydict_to_jsonld(answer_quality)}));
					
					// Show answer quality
					console.log('Answer quality:', answer_quality);
					if (answer_quality.semantic_similarity < 0.5)
					{
						self.warning_message = 'The following answers can be very imprecise. We struggled to extract them from data, maybe because this question cannot be properly answered using the available information.';
						self.show_warning_alert = true;
					}
				},
				error: function(result) {
					self.error_message = result;
					self.show_error_alert = true;
				},
			});
		},
	}
});

function summary_tree_to_jsonld(summary_tree) {
	var jsonld = {};
	for (var [key,value] of Object.entries(summary_tree))
	{
		if (key == 'children')
			continue;
		if (key == 'annotation')
		{
			if (value)
			{
				var source_id = prefixed_string_to_uri(summary_tree['source_id']);
				var jsonld_value = tuple_list_to_formatted_jsonld(value);
				var entity_dict = get_entity_dict_from_jsonld(jsonld_value);
				jsonld['my:hasSource'] = nest_jsonld(entity_dict[source_id], entity_dict, [source_id], 2);
			}
		}
		else
			jsonld['my:'+key] = value;
	}
	if (summary_tree.children && summary_tree.children.length)
		jsonld['my:sub_summary_list'] = summary_tree.children.map(summary_tree_to_jsonld);
	return jsonld;
}

function pydict_to_jsonld(pydict) {
	if (isDict(pydict))
	{
		var jsonld = {};
		for (var [key,value] of Object.entries(pydict))
			jsonld['my:'+key] = pydict_to_jsonld(value);
		return jsonld;
	}
	if (isArray(pydict))
		return pydict.map(pydict_to_jsonld);
	return pydict;
}

$(document).on('click', '.link', function(e) {
	var topic = e.target.dataset['topic'] || "";
	topic = uri_to_prefixed_string(topic);
	// var is_first = (e.target.dataset['is_first'] == 'true');
	var label = e.target.innerText;
	app.cards.push({
		'uri':topic,
		'label':titlefy(label),
		'deleted':false,
	});
	if (!app.show_overview_modal)
		app.current_card_index = app.cards.length-1;
	app.show_overview_modal = true;
});
