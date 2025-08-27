from rest_framework_simplejwt.authentication import JWTAuthentication

class StatelessUser:
    def __init__(self, payload):
        self.id = payload.get('id')
        self.username = payload.get('username')
        self.nome_usual = payload.get('nome_usual')
        self.tipo_vinculo = payload.get('tipo_vinculo')
        self.url_foto_75x100 = payload.get('url_foto_75x100')
        self.url_foto_150x200 = payload.get('url_foto_150x200')
        self.payload = payload

    def is_authenticated(self):
        return True

class StatelessJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        return StatelessUser(validated_token)
