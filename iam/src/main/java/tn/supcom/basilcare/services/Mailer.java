package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.mail.Authenticator;
import jakarta.mail.Message;
import jakarta.mail.MessagingException;
import jakarta.mail.PasswordAuthentication;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.util.Optional;
import java.util.Properties;
import java.util.logging.Logger;

/** Sends e-mail through SMTP, or logs it when smtp.enabled=false (development). */
@ApplicationScoped
public class Mailer {

    private static final Logger LOG = Logger.getLogger(Mailer.class.getName());

    @Inject
    @ConfigProperty(name = "smtp.enabled")
    boolean enabled;

    @Inject
    @ConfigProperty(name = "smtp.host")
    String host;

    @Inject
    @ConfigProperty(name = "smtp.port")
    int port;

    @Inject
    @ConfigProperty(name = "smtp.username")
    Optional<String> username;   // Optional: only required when enabled

    @Inject
    @ConfigProperty(name = "smtp.password")
    Optional<String> password;

    public void send(String to, String subject, String body) {
        if (!enabled) {
            LOG.info(() -> "[mail disabled] to=" + to + " subject=" + subject + " body=" + body);
            return;
        }
        Properties props = new Properties();
        props.put("mail.smtp.host", host);
        props.put("mail.smtp.port", String.valueOf(port));
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.starttls.enable", "true");
        Session session = Session.getInstance(props, new Authenticator() {
            @Override
            protected PasswordAuthentication getPasswordAuthentication() {
                return new PasswordAuthentication(username.orElseThrow(), password.orElseThrow());
            }
        });
        try {
            MimeMessage message = new MimeMessage(session);
            message.setFrom(new InternetAddress(username.orElseThrow()));
            message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(to));
            message.setSubject(subject);
            message.setText(body);
            Transport.send(message);
        } catch (MessagingException e) {
            throw new IllegalStateException("Could not send e-mail", e);
        }
    }
}