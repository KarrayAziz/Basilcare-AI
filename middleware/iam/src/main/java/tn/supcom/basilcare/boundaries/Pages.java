package tn.supcom.basilcare.boundaries;

import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

/** Serves the HTML pages from src/main/resources and builds error pages. */
final class Pages {

    private Pages() {
    }

    static Response page(String name) {
        return Response.ok(Pages.class.getResourceAsStream("/" + name), MediaType.TEXT_HTML).build();
    }

    static Response error(String message) {
        String safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
        return Response.status(Response.Status.BAD_REQUEST)
                .type(MediaType.TEXT_HTML)
                .entity("<!doctype html><meta charset=\"utf-8\"><title>BasilCare</title>"
                        + "<p style=\"font-family:sans-serif\">" + safe + "</p>")
                .build();
    }
}