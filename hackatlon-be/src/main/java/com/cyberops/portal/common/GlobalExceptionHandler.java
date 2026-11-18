package com.cyberops.portal.common;

import java.util.Map;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import jakarta.validation.ConstraintViolationException;

/** Error body: {"error": {"code": "...", "message": "..."}} */
@RestControllerAdvice
public class GlobalExceptionHandler {

	private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

	public static ResponseEntity<Map<String, Object>> error(HttpStatus status, String code, String message) {
		return ResponseEntity.status(status).body(Map.of("error", Map.of("code", code, "message", message)));
	}

	@ExceptionHandler({ NotFoundException.class, NoResourceFoundException.class })
	public ResponseEntity<Map<String, Object>> notFound(Exception e) {
		return error(HttpStatus.NOT_FOUND, "NOT_FOUND", e.getMessage());
	}

	@ExceptionHandler({ ForbiddenException.class, AccessDeniedException.class })
	public ResponseEntity<Map<String, Object>> forbidden(Exception e) {
		return error(HttpStatus.FORBIDDEN, "FORBIDDEN", e.getMessage());
	}

	@ExceptionHandler(MethodArgumentNotValidException.class)
	public ResponseEntity<Map<String, Object>> invalid(MethodArgumentNotValidException e) {
		String msg = e.getBindingResult().getFieldErrors().stream()
				.map(f -> f.getField() + ": " + f.getDefaultMessage())
				.collect(Collectors.joining("; "));
		return error(HttpStatus.BAD_REQUEST, "VALIDATION", msg);
	}

	@ExceptionHandler({ ConstraintViolationException.class, IllegalArgumentException.class,
			HttpMessageNotReadableException.class, MissingServletRequestParameterException.class,
			MethodArgumentTypeMismatchException.class })
	public ResponseEntity<Map<String, Object>> badRequest(Exception e) {
		return error(HttpStatus.BAD_REQUEST, "VALIDATION", String.valueOf(e.getMessage()));
	}

	@ExceptionHandler(Exception.class)
	public ResponseEntity<Map<String, Object>> internal(Exception e) {
		log.error("Unhandled error", e);
		return error(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL", "Beklenmeyen bir hata oluştu.");
	}
}
