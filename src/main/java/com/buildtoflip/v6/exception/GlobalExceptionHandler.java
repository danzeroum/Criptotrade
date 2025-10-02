package com.BuildToValue.v6.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;

import java.net.URI;
import java.time.Instant;
import java.util.UUID;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);
    private static final String TRACE_ID_KEY = "traceId";
    private static final MediaType PROBLEM_JSON = MediaType.valueOf("application/problem+json");

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ProblemDetail> handleBusinessException(
            BusinessException ex, WebRequest request) {
        ProblemDetail detail = ProblemDetail.forStatusAndDetail(
                HttpStatus.UNPROCESSABLE_ENTITY, ex.getMessage());

        enrichProblemDetail(detail, request, "business-error");
        logError(ex, detail);

        return ResponseEntity
                .status(HttpStatus.UNPROCESSABLE_ENTITY)
                .contentType(PROBLEM_JSON)
                .body(detail);
    }

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ProblemDetail> handleNotFoundException(
            ResourceNotFoundException ex, WebRequest request) {
        ProblemDetail detail = ProblemDetail.forStatusAndDetail(
                HttpStatus.NOT_FOUND, ex.getMessage());

        enrichProblemDetail(detail, request, "not-found");
        logError(ex, detail);

        return ResponseEntity
                .status(HttpStatus.NOT_FOUND)
                .contentType(PROBLEM_JSON)
                .body(detail);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ProblemDetail> handleGenericException(
            Exception ex, WebRequest request) {
        ProblemDetail detail = ProblemDetail.forStatusAndDetail(
                HttpStatus.INTERNAL_SERVER_ERROR,
                "An unexpected error occurred");

        enrichProblemDetail(detail, request, "internal-error");
        logError(ex, detail);

        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .contentType(PROBLEM_JSON)
                .body(detail);
    }

    private void enrichProblemDetail(
            ProblemDetail detail, WebRequest request, String type) {
        String traceId = MDC.get(TRACE_ID_KEY);
        if (traceId == null) {
            traceId = UUID.randomUUID().toString();
            MDC.put(TRACE_ID_KEY, traceId);
        }

        detail.setType(URI.create("https://api.example.com/errors/" + type));
        detail.setInstance(URI.create(request.getDescription(false)
                .replace("uri=", "")));
        detail.setProperty("traceId", traceId);
        detail.setProperty("timestamp", Instant.now());
    }

    private void logError(Exception ex, ProblemDetail detail) {
        logger.error("""
            {
                "timestamp": "{}",
                "level": "ERROR",
                "traceId": "{}",
                "type": "{}",
                "status": {},
                "message": "{}",
                "exception": "{}"
            }
            """,
                Instant.now(),
                detail.getProperties().get("traceId"),
                detail.getType(),
                detail.getStatus(),
                detail.getDetail(),
                ex.getClass().getSimpleName()
        );
    }
}
