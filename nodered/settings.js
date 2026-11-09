/**
 * Node-RED settings for BasilCare. Only what differs from the defaults is here.
 * All options: https://nodered.org/docs/user-guide/runtime/settings-file
 *
 * Secrets never go in this file: they come from environment variables
 * (deploy/compose.yaml in development, the server's .env in production).
 */
module.exports = {
    // This folder is mounted as /data, so "Deploy" in the editor writes the
    // repository's nodered/flows.json directly.
    flowFile: "flows.json",

    // Indented JSON, so "git diff" shows exactly which node changed.
    flowFilePretty: true,

    // Key that encrypts flows_cred.json (broker or API passwords).
    // Not set in development: Node-RED then generates one in .config.runtime.json.
    credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET || undefined,   // "" counts as not set

    // Editor login. Without it, anyone who reaches port 1880 can change the
    // flows and run code: set NODE_RED_ADMIN_HASH before any Internet exposure.
    // Make the hash with: docker compose exec nodered node-red admin hash-pw
    adminAuth: process.env.NODE_RED_ADMIN_HASH ? {
        type: "credentials",
        users: [{ username: "admin", password: process.env.NODE_RED_ADMIN_HASH, permissions: "*" }],
    } : undefined,

    uiPort: 1880,

    logging: {
        console: { level: "info", metrics: false, audit: false },
    },

    editorTheme: {
        projects: { enabled: false },   // Git is handled outside Node-RED
    },
};
