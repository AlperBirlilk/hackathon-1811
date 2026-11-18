package com.cyberops.portal.auth;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/** Guards /internal/** with header X-Service-Key == portal.service-key (Django -> Java calls). */
public class ServiceKeyFilter extends OncePerRequestFilter {

	public static final String HEADER = "X-Service-Key";

	private final byte[] expected;

	public ServiceKeyFilter(String serviceKey) {
		this.expected = serviceKey.getBytes(StandardCharsets.UTF_8);
	}

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		return !request.getRequestURI().startsWith(request.getContextPath() + "/internal/");
	}

	@Override
	protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
			throws ServletException, IOException {
		String given = request.getHeader(HEADER);
		if (given == null || !MessageDigest.isEqual(expected, given.getBytes(StandardCharsets.UTF_8))) {
			response.setStatus(HttpServletResponse.SC_FORBIDDEN);
			response.setContentType("application/json");
			response.getWriter().write("{\"error\":{\"code\":\"FORBIDDEN\",\"message\":\"Invalid service key\"}}");
			return;
		}
		chain.doFilter(request, response);
	}
}
