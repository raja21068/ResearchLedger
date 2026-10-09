from referee.contracts import validate_json_contract


def test_local_validator_enforces_const_pattern_bounds_and_uniqueness():
    schema={
      'type':'object','additionalProperties':False,'required':['version','id','confidence','ids'],
      'properties':{
        'version':{'const':'v1'},'id':{'type':'string','pattern':'^MC[0-9]{3,}$'},
        'confidence':{'type':'number','minimum':0.0,'maximum':1.0},
        'ids':{'type':'array','uniqueItems':True,'items':{'type':'string'}}}}
    assert validate_json_contract({'version':'v1','id':'MC001','confidence':0.8,'ids':['A','B']},schema)==[]
    errors=validate_json_contract({'version':'v2','id':'M1','confidence':1.2,'ids':['A','A'],'extra':1},schema)
    joined='; '.join(errors)
    assert 'const' in joined and 'pattern' in joined and 'maximum' in joined and 'uniqueItems' in joined and 'additional property' in joined
