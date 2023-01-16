import math
import json
from models.model_manager import ModelManager

class NeuralSentenceSummariser(ModelManager):

	def __init__(self, model_options):
		model_options['hf_model']['type'] = 'summarization'
		super().__init__(model_options)
		self.debug = model_options.get('debug',False)
		self.max_input_token_count = self.get_hf_model()['config'].max_position_embeddings

	@staticmethod
	def sentify(s):
		return ' '.join((
			p[0].upper() + p[1:] + ('.' if p[-1] != '.' else '')
			for p in s.split(' . ')
			if p
		))

	def summarise_sentence(self, sentence, sentence_id=None, n=1, options=None, min_size=None):
		# if len(sentence) < 100:
		# 	return (sentence,)
		if not options:
			options = {}
		# Format sentence
		tokenizer = self.get_hf_model()['tokenizer']
		tokenized_sentence = tokenizer.convert_ids_to_tokens(tokenizer.encode(sentence))
		if min_size and len(tokenized_sentence) < min_size:
			return (sentence,)
		tokenized_sentence = tokenized_sentence[:self.max_input_token_count-3] # the 1st and last token are a BoS (Begin of String) and a EoS (End of String), furthermore a task token is added to the beginning of the sentence
		formatted_sentence = tokenizer.convert_tokens_to_string(tokenized_sentence)
		# print(formatted_sentence)
		# sentence = ' '.join(sentence.split(' ')[:self.max_input_token_count])
		summary_ids = self.run_hf_task(
			[formatted_sentence], 
			min_length=3, 
			max_length=self.max_input_token_count, 
			num_return_sequences=n, # default 1
			**options
			# do_sample=True, # default False
		)[0]
		return tuple(map(lambda x: x['summary_text'], summary_ids))

	@staticmethod
	def integrate_summary_tree_list(integration_map, summary_tree_list):
		for summary_tree in summary_tree_list:
			sentence = summary_tree.get('sentence',None)
			if sentence:
				integration = integration_map.get(sentence, None)
				if integration:
					summary_tree.update(integration)
			if 'children' in summary_tree:
				NeuralSentenceSummariser.integrate_summary_tree_list(integration_map, summary_tree['children'])

	def summarise_sentence_list(self, sentence_list, tree_arity=2, cut_factor=1, depth=None, options=None, min_size=None):
		def get_elements_to_merge(slist, merge_size):
			# slist = tuple(filter(lambda x: x[-1]=='.', slist))
			return tuple(
				slist[i:i+merge_size]
				for i in range(0,len(slist),merge_size)
			)

		root_set = tuple(map(
			lambda s: self.summarise_sentence(s, n=1, options=options, min_size=min_size)[0], 
			sentence_list
		))
		root_set = tuple(map(
			self.sentify, 
			root_set
		))
		summary_tree = [
			{
				'summary': k,
				'children': [{'sentence':v}]
			}
			for k,v in zip(root_set, sentence_list)
		]
		limit = 1 if not depth else math.ceil(len(root_set)/(tree_arity**depth))
		while len(root_set) > limit:
			root_set = tuple(
				self.summarise_sentence(
					' '.join(map(self.sentify, etm)), 
					n=1, 
					options=options,
					min_size=min_size
				)[0] if len(etm) > 1 else etm[0]
				for etm in get_elements_to_merge(root_set, tree_arity)	
			)
			root_set = tuple(map(self.sentify, root_set))
			summary_tree = [
				{
					'summary': summary,
					'children': summary_tree[i*tree_arity:(i+1)*tree_arity]
				}
				for i,summary in enumerate(root_set)
			]
			if cut_factor > 1 and len(root_set) > 2:
				root_set = root_set[:math.ceil(len(root_set)/cut_factor)]
		# print(json.dumps(summary_tree, indent=4))
		return summary_tree
