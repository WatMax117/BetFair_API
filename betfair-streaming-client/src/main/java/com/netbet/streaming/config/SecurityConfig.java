package com.netbet.streaming.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Production guard for /metadata/** endpoints.
 * - /metadata/** requires ROLE_ADMIN (HTTP Basic or integrate with your auth).
 * - /cache/** remains open for debugging (optional: restrict at reverse proxy).
 *
 * TODO (Production): Prefer restricting /metadata/** at the Reverse Proxy (Nginx) level:
 *   - Allow only internal IP range (e.g. 10.0.0.0/8, 172.16.0.0/12) or VPN.
 *   - Or require a shared secret header (e.g. X-Internal-Token) and validate in Nginx.
 *   Example Nginx: location /metadata/ { allow 10.0.0.0/8; deny all; proxy_pass ...; }
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Value("${betfair.metadata-admin-user:admin}")
    private String metadataAdminUser;

    @Value("${betfair.metadata-admin-password:changeme}")
    private String metadataAdminPassword;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/metadata/**").hasRole("ADMIN")
                        .requestMatchers("/cache/**", "/error", "/actuator/**", "/**").permitAll()
                )
                .httpBasic(basic -> {});
        return http.build();
    }

    @Bean
    public UserDetailsService userDetailsService(PasswordEncoder encoder) {
        UserDetails admin = User.builder()
                .username(metadataAdminUser)
                .password(encoder.encode(metadataAdminPassword))
                .roles("ADMIN")
                .build();
        return new InMemoryUserDetailsManager(admin);
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return PasswordEncoderFactories.createDelegatingPasswordEncoder();
    }
}
