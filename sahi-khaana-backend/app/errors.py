"""One exception type for every error the API returns on purpose.

The global handlers in main.py turn it into:
    {"error": {"code": "...", "message": "..."}}
"""


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


# Convenience constructors for the codes the Flutter app must handle.
def poor_image(message: str) -> AppError:
    return AppError("POOR_IMAGE", message, 422)


def no_text_found() -> AppError:
    return AppError("NO_TEXT_FOUND", "No readable text was found in the image.", 422)


def no_ingredients_section() -> AppError:  # used from Phase 2
    return AppError(
        "NO_INGREDIENTS_SECTION",
        "Could not find an ingredients section in the text.",
        422,
    )


def invalid_file(message: str) -> AppError:
    return AppError("INVALID_FILE", message, 400)


def file_too_large(max_bytes: int) -> AppError:
    return AppError(
        "FILE_TOO_LARGE",
        f"Image is larger than the {max_bytes // (1024 * 1024)} MB limit.",
        413,
    )
