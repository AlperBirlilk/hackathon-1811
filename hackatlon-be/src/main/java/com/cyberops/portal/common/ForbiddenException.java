package com.cyberops.portal.common;

public class ForbiddenException extends RuntimeException {
	public ForbiddenException(String message) {
		super(message);
	}

	public ForbiddenException() {
		this("Bu işlem için yetkiniz yok.");
	}
}
