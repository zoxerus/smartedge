import json
def enum_dictionary_to_json_string(dic_obj):
    return json.dumps({key.value: value for key, value in dic_obj.items()})
    