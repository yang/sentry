from drf_spectacular.utils import OpenApiExample

serialized_om_example = {
    "id": "8",
    "email": "dummy@example.com",
    "name": "dummy@example.com",
    "user": {
        "id": "5",
        "name": "dummy@example.com",
        "username": "dummy@example.com",
        "email": "dummy@example.com",
        "avatarUrl": "https://secure.gravatar.com/avatar/6e8e0bf6135471802a63a17c5e74ddc5?s=32&d=mm",
        "isActive": True,
        "hasPasswordAuth": True,
        "isManaged": False,
        "dateJoined": "2022-02-24T05:00:50.796399Z",
        "lastLogin": "2022-02-24T05:00:50.818081Z",
        "has2fa": False,
        "lastActive": "2022-02-24T05:00:50.796406Z",
        "isSuperuser": False,
        "isStaff": True,
        "experiments": {},
        "emails": [{"id": "5", "email": "dummy@example.com", "is_verified": True}],
        "avatar": {"avatarType": "letter_avatar", "avatarUuid": None},
    },
    "role": "member",
    "roleName": "Member",
    "pending": False,
    "expired": False,
    "flags": {
        "sso:linked": False,
        "sso:invalid": False,
        "member-limit:restricted": False,
    },
    "dateCreated": "2022-02-24T05:00:50.811995Z",
    "inviteStatus": "approved",
    "inviterName": None,
}


basic_get_index_example = OpenApiExample(
    "Retrieve a List of Organization Members",
    response_only=True,
    value=[serialized_om_example],
    status_codes=["200"],
)

basic_put_details_example = OpenApiExample(
    "Update an Organization Member",
    response_only=True,
    value=serialized_om_example,
    status_codes=["200"],
)
