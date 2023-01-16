import Levenshtein

def remove_similar_labels(tuple_list, threshold=0.3):
	fetch_value = lambda x: x[0] if isinstance(x, (list,tuple)) else x
	new_tuple_list = []
	for t in tuple_list:
		is_unique = True
		for other_t in new_tuple_list:
			if labels_are_similar(fetch_value(t),fetch_value(other_t),threshold):
				is_unique = False
				break
		if is_unique:
			new_tuple_list.append(t)
	return new_tuple_list

def get_normalized_sintactic_distance(a,b):
	return Levenshtein.distance(a,b)/max(len(a),len(b))

def labels_are_similar(a,b, threshold=0.3):
	return get_normalized_sintactic_distance(a,b) < threshold

def get_most_similar_label(label,other_label_list):
	distance, most_similar_label = min(map(lambda x: (Levenshtein.distance(label,x),x), other_label_list), key=lambda x:x[0])
	return most_similar_label# if min(1.,distance/len(label)) < 0.2 else label
