# Overridding Email Templates
The documentation on this topic is here: https://docs.allauth.org/en/latest/common/email.html

The way to override any email is to:

look at the messages here: https://github.com/pennersr/django-allauth/tree/65.4.1/allauth/templates/account/email
find the email content that we want to override
create a new .html file inside of the templates/account/email directory of the same name
utilize the context available in the .txt version to bring into the html version.
This PR overrides both of the ways allauth sends email verification. One version is directly after signup. The other would be if they need to re-trigger an email verification after the sign up flow.