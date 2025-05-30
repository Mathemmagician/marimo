# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Optional, Union

import marimo._output.data.data as mo_data
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import create_style, normalize_dimension
from marimo._plugins.core.media import io_to_data_url

Image = Union[str, bytes, io.BytesIO, io.BufferedReader, Path]
# Union[list, torch.Tensor, jax.numpy.ndarray,
#             np.ndarray, scipy.sparse.spmatrix]
Tensor = Any
ImageLike = Union[Image, Tensor]


def _normalize_image(src: ImageLike) -> Image:
    """Normalize an image-like object to a standard format.

    This function handles a variety of input types, including lists, arrays,
    and tensors, and converts them to a BytesIO object representing a PNG
    image.

    Typical convention for handling images is to use `PIL`, which is exactly
    what `matplotlib` does behind the scenes. `PIL` requires a `ndarray`
    (validated with the numpy specific `__array_interface__` attribute). In
    turn, numpy can cast lists, and objects with the `__array__` method (like
    jax, torch tensors). `scipy.sparse` breaks this convention but does have a
    `toarray` method, which is general enough that a specific check is
    performed here.

    Args:
        src: An image-like object. This can be a list, array, tensor, or a
            file-like object.

    Returns:
        A BytesIO object or other Image type.

    Raises:
        ModuleNotFoundError: If the required `PIL` or `numpy` packages are not
            available.
        ValueError: If the input is not a valid image-like object.
    """
    if (
        isinstance(src, list)
        or hasattr(src, "__array__")
        or hasattr(src, "toarray")
    ):
        DependencyManager.pillow.require(
            "to render images from arrays in `mo.image`"
        )
        from PIL import Image as _Image

        if not hasattr(src, "__array_interface__"):
            DependencyManager.numpy.require(
                "to render images from generic arrays in `mo.image`"
            )
            import numpy

            # Capture those sparse cases
            if hasattr(src, "toarray"):
                src = src.toarray()
            src = numpy.array(src)
        src = (src - src.min()) / (src.max() - src.min()) * 255.0
        img = _Image.fromarray(src.astype("uint8"))
        # io.BytesIO is one of the Image types.
        normalized_src: Image = io.BytesIO()
        img.save(normalized_src, format="PNG")
        return normalized_src

    # Handle PIL Image objects
    if DependencyManager.pillow.imported():
        from PIL import Image as _Image

        if isinstance(src, _Image.Image):
            img_byte_arr = io.BytesIO()
            src.save(img_byte_arr, format=src.format or "PNG")
            img_byte_arr.seek(0)
            return img_byte_arr

    # Verify that this is a image object
    if not isinstance(src, (str, bytes, io.BytesIO, io.BufferedReader, Path)):
        raise ValueError(
            f"Expected an image object, but got {type(src)} instead."
        )
    return src


@mddoc
def image(
    src: ImageLike,
    alt: Optional[str] = None,
    width: Optional[Union[int, str]] = None,
    height: Optional[Union[int, str]] = None,
    rounded: bool = False,
    style: Optional[dict[str, Any]] = None,
    caption: Optional[str] = None,
) -> Html:
    """Render an image as HTML.

    Examples:
        ```python3
        # Render an image from a local file
        mo.image(src="path/to/image.png")
        ```

        ```python3
        # Render an image from a URL
        mo.image(
            src="https://marimo.io/logo.png",
            alt="Marimo logo",
            width=100,
            height=100,
            rounded=True,
            caption="Marimo logo",
        )
        ```

    Args:
        src: a path or URL to an image, a file-like object
            (opened in binary mode), or array-like object.
        alt: the alt text of the image
        width: the width of the image in pixels or a string with units
        height: the height of the image in pixels or a string with units
        rounded: whether to round the corners of the image
        style: a dictionary of CSS styles to apply to the image
        caption: the caption of the image

    Returns:
        `Html` object
    """
    # Convert to virtual file
    resolved_src: Optional[str]
    src = _normalize_image(src)
    # TODO: Consider downsampling here. This is something matplotlib does
    # implicitly, and can potentially remove the bottle-neck of very large
    # images.
    if isinstance(src, io.BufferedReader) or isinstance(src, io.BytesIO):
        src.seek(0)
        resolved_src = mo_data.image(src.read()).url
    elif isinstance(src, bytes):
        resolved_src = mo_data.image(src).url
    elif isinstance(src, Path):
        resolved_src = mo_data.image(src.read_bytes(), ext=src.suffix).url
    elif isinstance(src, str) and os.path.isfile(
        expanded_path := os.path.expanduser(src)
    ):
        src = Path(expanded_path)
        resolved_src = mo_data.image(src.read_bytes(), ext=src.suffix).url
    else:
        resolved_src = io_to_data_url(src, fallback_mime_type="image/png")

    styles = create_style(
        {
            "width": normalize_dimension(width),
            "height": normalize_dimension(height),
            "border-radius": "4px" if rounded else None,
            **(style or {}),
        }
    )
    img = h.img(src=resolved_src, alt=alt, style=styles)
    if caption is not None:
        return Html(
            h.figure(
                [
                    img,
                    h.figcaption(
                        [caption],
                        style="color: var(--muted-foreground); "
                        "text-align: center; margin-top: 0.5rem;",
                    ),
                ],
                style="display: flex; flex-direction: column;",
            )
        )
    return Html(img)
