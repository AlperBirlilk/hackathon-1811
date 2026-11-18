package com.cyberops.portal;

import java.io.File;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class PortalApplication {

	public static void main(String[] args) {
		// DuckDB needs the parent directory of the database file to exist.
		new File("data").mkdirs();
		SpringApplication.run(PortalApplication.class, args);
	}
}
