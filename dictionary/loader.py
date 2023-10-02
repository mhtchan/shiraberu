import json
import zipfile
from peewee import (
    IntegrityError,
    Model,
    SqliteDatabase,
    AutoField,
    TextField,
    BooleanField,
    IntegerField,
    ForeignKeyField,
    SQL,
    fn,
    chunked,
)
from playhouse.sqlite_ext import JSONField, SearchField, FTS5Model, RowIDField
import re
from sqlitefts import fts5
from itertools import combinations

db = SqliteDatabase('dictionary_fts.db',autoconnect=True)

class SimpleTokenizer(fts5.FTS5Tokenizer):
    def __init__(self, **kwargs):
        self.tokenize_flag = kwargs.get('tokenize_flag', True)

    def tokenize(self, text, flags=None):
        if not self.tokenize_flag:
            yield text, 0, len(text.encode('utf-8'))
        else:
            length = len(text) + 1
            for s,e in combinations(range(length), r=2):
                t = text[s:e]
                l = len(t.encode('utf-8'))
                p = len(text[:s].encode('utf-8'))
                yield t, p, p + l

def register_tokenizer(db, tokenize_flag=True):
    tk = fts5.make_fts5_tokenizer(SimpleTokenizer(tokenize_flag=tokenize_flag))
    conn = db.connection()
    conn.enable_load_extension(True)
    fts5.register_tokenizer(conn, 'simple_tokenizer', tk)

def yomichan_export_to_dict(d):
    return dict(zip(Entry._meta.sorted_field_names[2:],d))

def load_dictionary(path='dictionary_files/daijirin.zip'):
    try:
        with db:
            #db.connect(reuse_if_open=True)
            register_tokenizer(db)
            db.create_tables([Dictionary, Entry, EntryFTS])
            
            with zipfile.ZipFile(path) as z:
                with z.open("index.json", mode="r") as f:
                    dictionary = Dictionary(**json.load(f))
                    dictionary.save()
                    
                    # After inserting, set the priority to be last (same as the insert row id)
                    dictionary_id = dictionary.get_id()
                    print(f"Loaded dictionary with {dictionary_id=}")
                    q = Dictionary.\
                        update({Dictionary.priority: dictionary_id}).\
                        where(Dictionary.id == dictionary_id)
                    q.execute()
                ## Insert Entry data
                print("Inserting data into Entry table")
                for filename in z.namelist():
                    if filename.startswith("term_bank_"):
                        with z.open(filename, mode="r") as f:
                            data = json.load(f)
                            data = [{"dictionary_id": dictionary.id, **yomichan_export_to_dict(i)} for i in data]
                            with db.atomic():
                                for batch in chunked(data, 100):
                                    Entry.insert_many(batch, list(Entry._meta.fields.keys())[1:]).execute()
                        print(filename)
    
                ## Insert EntryFTS data
                print("Inserting data into EntryFTS table")
                query = Entry\
                    .select(
                        Entry.id,
                        Entry.expression,
                        Entry.reading,
                     ).where(
                        Entry.dictionary_id == dictionary_id
                     )
                EntryFTS.insert_from(query, EntryFTS._meta.fields.keys()).execute()
    except IntegrityError as e:
        if str(e).startswith("UNIQUE constraint failed"):
            print("Dictionary has already been loaded.")
        else:
            raise
    finally:
        db.close()

def remove_dictionary(*dictionary_ids):
    for dictionary_id in dictionary_ids:
        q = Dictionary.delete().where(Dictionary.id == dictionary_id)
        q.execute()

        q = EntryFTS.delete().where(EntryFTS.rowid << Entry.select(Entry.id).where(Entry.dictionary_id == dictionary_id))
        q.execute()        

        q = Entry.delete().where(Entry.dictionary_id == dictionary_id)
        q.execute()

def remove_all_dictionaries():
    q = Dictionary.delete()
    q.execute()
    
    q = Entry.delete()
    q.execute()
    
    q = EntryFTS.delete()
    q.execute()

def update_dictionary_priority(dictionary_id, new_priority):
    q = Dictionary.update({Dictionary.priority: new_priority}).where(Dictionary.id == dictionary_id)
    q.execute()

def get_definition(term, max_return=300):
    db.connect(reuse_if_open=True)
    register_tokenizer(db, tokenize_flag=False)
    term = term.replace('％','%').replace('＿','_')
    _tokens = re.split('_|%',term)
    tokens = [i for i in _tokens if i!='']

    if len(_tokens) > 1:
        result = Entry\
            .select(
                Entry.expression,
                Entry.reading,
                fn.json_group_array(
                    fn.json_object(
                  		'dictionary_id', Entry.dictionary_id,
                        'dictionary_name', Dictionary.title,
                        'dictionary_priority', Dictionary.priority,
                        'definition_tags', Entry.definition_tags,
                        'rules', Entry.rules,
                        'score', Entry.score,
                        'glossary', Entry.glossary,
                        'sequence', Entry.sequence,
                        'term_tags', Entry.term_tags
                    )
                ).python_value(json.loads).alias('definitions')
            )\
            .join(Dictionary, on=(Entry.dictionary_id==Dictionary.id))\
            .join(EntryFTS, on=(Entry.id==EntryFTS.rowid))\
            .where(
                EntryFTS.match(' AND '.join(tokens)) &
                ((Entry.expression ** term) | (Entry.reading ** term))
            )\
            .group_by(
                Entry.expression,
                Entry.reading
            )\
            .order_by(
                fn.length(Entry.expression)
            )\
            .limit(max_return)
        return result
    result = Entry\
        .select(
            Entry.expression,
            Entry.reading,
            fn.json_group_array(
                fn.json_object(
              		'dictionary_id', Entry.dictionary_id,
                    'dictionary_name', Dictionary.title,
                    'dictionary_priority', Dictionary.priority,
                    'definition_tags', Entry.definition_tags,
                    'rules', Entry.rules,
                    'score', Entry.score,
                    'glossary', Entry.glossary,
                    'sequence', Entry.sequence,
                    'term_tags', Entry.term_tags
                )
            ).python_value(json.loads).alias('definitions')
        )\
        .join(Dictionary, on=(Entry.dictionary_id==Dictionary.id))\
        .where((Entry.expression==term) | (Entry.reading==term))\
        .group_by(
            Entry.expression,
            Entry.reading
        )\
        .order_by(
            fn.length(Entry.expression)
        )\
        .limit(max_return)
    return result

class Dictionary(Model):
    id = AutoField(unique=True)
    title = TextField()
    format = TextField()
    revision = TextField()
    sequenced = BooleanField()
    priority = IntegerField(index=True, null=True)

    class Meta:
        database = db
        table_name = "dictionary"
        constraints = [SQL('UNIQUE (title,format,revision)')]

class Entry(Model):
    id = AutoField(unique=True)
    dictionary_id = ForeignKeyField(Dictionary, to_field="id", index=True)
    expression = TextField(index=False) # redundant from the composite index
    reading = TextField(index=True)
    definition_tags = TextField()
    rules = TextField()
    score = IntegerField()
    glossary = JSONField()
    sequence = IntegerField()
    term_tags = TextField()

    class Meta:
        database = db
        table_name = "entry"
        indexes = (
            (('expression', 'reading'), False),
        )

class EntryFTS(FTS5Model):
    rowid = RowIDField()
    expression = SearchField()
    reading = SearchField()

    class Meta:
        database = db
        table_name = "entry_fts"
        options = {'tokenize': 'simple_tokenizer'}
        
if __name__ == "__main__":
    load_dictionary(path='dictionary_files/daijirin.zip')
    load_dictionary(path='dictionary_files/daijisen.zip')
    load_dictionary(path='dictionary_files/kojien.zip')
    load_dictionary(path='dictionary_files/meikyou.zip')
    load_dictionary(path='dictionary_files/jmdict.zip')