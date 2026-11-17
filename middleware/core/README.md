# Shared middleware code

This directory is reserved for code genuinely shared by the API and IAM modules.
It currently contains no Java implementation or Maven artifact: both applications
still build independently and produce `api.war` and `iam.war`.

Introduce a shared library here when a concrete shared responsibility is identified.
Do not move API-only or IAM-only business rules here just to populate the directory.
