from . import DbTerminator, Terminator


class PollyLexicon(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_polly_lexicons(client):
            results = client.list_lexicons()
            next_token = results.pop('NextToken', None)
            while next_token:
                next_lexicons = client.list_lexicons(NextToken=next_token)
                next_token = next_lexicons.pop('NextToken', None)
                results['Lexicons'].append(next_lexicons['Lexicons'])
            return results.get('Lexicons', [])
        return Terminator._create(credentials, PollyLexicon, 'polly', _paginate_polly_lexicons)

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['Attributes']['LastModified']

    def terminate(self):
        self.client.delete_lexicon(Name=self.name)


class RekognitionCollection(DbTerminator):
    @staticmethod
    def create(credentials):
        def _paginate_rekognition_collections(client):
            return client.get_paginator('list_collections').paginate().build_full_result()['CollectionIds']
        return Terminator._create(credentials, RekognitionCollection, 'rekognition', _paginate_rekognition_collections)

    @property
    def id(self):
        return self.instance

    @property
    def name(self):
        return self.instance

    def terminate(self):
        self.client.delete_collection(CollectionId=self.id)
