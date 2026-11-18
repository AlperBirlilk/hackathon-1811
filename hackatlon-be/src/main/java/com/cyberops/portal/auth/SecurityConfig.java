package com.cyberops.portal.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.http.HttpStatus;

@Configuration
public class SecurityConfig {

	@Bean
	JwtDecoder jwtDecoder(JwtService jwtService) {
		return jwtService.decoder();
	}

	@Bean
	SecurityFilterChain securityFilterChain(HttpSecurity http, @Value("${portal.service-key}") String serviceKey)
			throws Exception {
		http.csrf(c -> c.disable())
				.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
				.httpBasic(b -> b.disable())
				.formLogin(f -> f.disable())
				.addFilterBefore(new ServiceKeyFilter(serviceKey), UsernamePasswordAuthenticationFilter.class)
				.authorizeHttpRequests(a -> a
						// /internal/** is guarded by ServiceKeyFilter
						.requestMatchers("/internal/**").permitAll()
						.requestMatchers("/v3/api-docs/**", "/swagger-ui/**", "/swagger-ui.html", "/actuator/health",
								"/error")
						.permitAll()
						.requestMatchers("/api/**").authenticated()
						.anyRequest().denyAll())
				.oauth2ResourceServer(o -> o.jwt(j -> {
				}).authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
				.exceptionHandling(e -> e.authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)));
		return http.build();
	}
}
