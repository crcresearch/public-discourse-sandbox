TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'public_discourse_sandbox.pds_app.context_processors.active_bots',
                'public_discourse_sandbox.pds_app.context_processors.user_experiments',
                'public_discourse_sandbox.pds_app.context_processors.is_moderator',
            ],
        },
    },
] 