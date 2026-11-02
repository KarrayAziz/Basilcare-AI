package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.repositories.TenantRepository;
import tn.supcom.basilcare.services.RegistrationService;

/** Sign-up: GET form, POST account, POST activation code. */
@Path("register")
public class RegistrationEndpoint {

    @Inject
    TenantRepository tenants;

    @Inject
    RegistrationService registration;

    @GET
    @Produces(MediaType.TEXT_HTML)
    public Response form(@QueryParam("client_id") String clientId) {
        if (clientId == null || tenants.findById(clientId).isEmpty()) {
            return Pages.error("Unknown application.");
        }
        return Pages.page("signup.html");
    }

    @POST
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.TEXT_HTML)
    public Response register(@FormParam("username") String username,
                             @FormParam("email") String email,
                             @FormParam("password") String password) {
        try {
            registration.register(username, email, password);
            return Pages.page("activate.html");
        } catch (IllegalArgumentException e) {
            return Pages.error(e.getMessage());
        }
    }

    @POST
    @Path("activate")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.TEXT_HTML)
    public Response activate(@FormParam("username") String username,
                             @FormParam("code") String code) {
        try {
            registration.activate(username, code);
            return Pages.page("activated.html");
        } catch (IllegalArgumentException e) {
            return Pages.error(e.getMessage());
        }
    }
}