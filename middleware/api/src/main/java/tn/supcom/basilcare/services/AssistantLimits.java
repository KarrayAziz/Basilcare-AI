package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Semaphore;

/** Per-process limits: six requests/user/minute and two concurrent upstream requests. */
@ApplicationScoped
public class AssistantLimits {
    private record Window(long started, int count) { }
    private final Map<String, Window> users = new HashMap<>();
    private final Semaphore slots = new Semaphore(2);

    public synchronized boolean allow(String user, long now) {
        users.entrySet().removeIf(e -> now - e.getValue().started() >= 60_000);
        Window window = users.get(user);
        if (window == null && users.size() >= 1024) return false;
        if (window != null && window.count() >= 6) return false;
        users.put(user, new Window(window == null ? now : window.started(), window == null ? 1 : window.count() + 1));
        return true;
    }

    public boolean acquire() { return slots.tryAcquire(); }
    public void release() { slots.release(); }
}
