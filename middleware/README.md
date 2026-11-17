# Middleware

- [core](core/README.md): reserved for shared server code; no implementation yet.
- [api](api/README.md): REST API, data ingestion and application business rules.
- [iam](iam/README.md): accounts, authentication and access tokens.

From the repository root:

```bash
mvn --file middleware/iam/pom.xml verify
mvn --file middleware/api/pom.xml verify
```

The output files remain `middleware/iam/target/iam.war` and
`middleware/api/target/api.war`; WildFly still exposes `/iam/` and `/api/`.
