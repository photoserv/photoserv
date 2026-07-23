from mozilla_django_oidc.auth import OIDCAuthenticationBackend

class OIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        """Create a user from OIDC claims."""
        first_user = not self.UserModel.objects.exists()
        user = super().create_user(claims)
        user.username = self.get_username(claims)
        user.first_name = self.get_first_name(claims)
        user.last_name = self.get_given_name(claims)
        if first_user:
            user.is_staff = True
            user.is_superuser = True
        user.save()
        return user

    def update_user(self, user, claims):
        """Update user each login to sync username."""
        only_user = self.UserModel.objects.count() == 1
        user = super().update_user(user, claims)
        user.username = self.get_username(claims)
        user.first_name = self.get_first_name(claims)
        user.last_name = self.get_given_name(claims)
        if only_user:
            user.is_staff = True
            user.is_superuser = True
        user.save()
        return user

    def get_username(self, claims):
        """
        Decide which claim to use for the Django username.
        """
        return (
            claims.get("preferred_username")
            or claims.get("username")
            or claims.get("email")
            or claims.get("sub")
        )

    def get_first_name(self, claims):
        return claims["name"].split()[0]

    def get_given_name(self, claims):
        arr = claims["name"].split()

        if len(arr) == 1:
            return ""
        
        return " ".join(arr[1:])