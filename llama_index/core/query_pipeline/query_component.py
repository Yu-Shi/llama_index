"""Pipeline schema."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set, Union

from llama_index.bridge.pydantic import BaseModel, Field
from llama_index.core.llms.types import ChatResponse, CompletionResponse
from llama_index.core.response.schema import Response
from llama_index.schema import QueryBundle

## Define common types used throughout these components
StringableInput = Union[CompletionResponse, ChatResponse, str, QueryBundle, Response]


def validate_and_convert_stringable(input: Any) -> str:
    """Validate and convert stringable input."""
    if not isinstance(input, StringableInput):
        raise ValueError(f"Input {input} is not stringable.")
    return str(input)


class InputKeys(BaseModel):
    """Input keys."""

    required_keys: Set[str] = Field(default_factory=set)
    optional_keys: Set[str] = Field(default_factory=set)

    @classmethod
    def from_keys(
        cls, required_keys: Set[str], optional_keys: Optional[Set[str]] = None
    ) -> "InputKeys":
        """Create InputKeys from tuple."""
        return cls(required_keys=required_keys, optional_keys=optional_keys or set())

    def validate(self, input_keys: Set[str]) -> None:
        """Validate input keys."""
        # check if required keys are present, and that keys all are in required or optional
        if not self.required_keys.issubset(input_keys):
            raise ValueError(
                f"Required keys {self.required_keys} are not present in input keys {input_keys}"
            )
        if not input_keys.issubset(self.required_keys.union(self.optional_keys)):
            raise ValueError(
                f"Input keys {input_keys} contain keys not in required or optional keys {self.required_keys.union(self.optional_keys)}"
            )

    def __len__(self) -> int:
        """Length of input keys."""
        return len(self.required_keys) + len(self.optional_keys)

    def all(self) -> Set[str]:
        """Get all input keys."""
        return self.required_keys.union(self.optional_keys)


class OutputKeys(BaseModel):
    """Output keys."""

    required_keys: Set[str] = Field(default_factory=set)

    @classmethod
    def from_keys(
        cls,
        required_keys: Set[str],
    ) -> "InputKeys":
        """Create InputKeys from tuple."""
        return cls(required_keys=required_keys)

    def validate(self, input_keys: Set[str]) -> None:
        """Validate input keys."""
        # validate that input keys exactly match required keys
        if input_keys != self.required_keys:
            raise ValueError(
                f"Input keys {input_keys} do not match required keys {self.required_keys}"
            )


class ChainableMixin(ABC):
    """Chainable mixin.

    A module that can produce a `QueryComponent` from a set of inputs through
    `as_query_component`.

    If plugged in directly into a `QueryPipeline`, the `ChainableMixin` will be
    converted into a `QueryComponent` with default parameters.

    """

    @abstractmethod
    def _as_query_component(self, **kwargs: Any) -> "QueryComponent":
        """Get query component."""

    def as_query_component(
        self, partial: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> "QueryComponent":
        """Get query component."""
        component = self._as_query_component(**kwargs)
        component.partial(**(partial or {}))
        return component


class QueryComponent(BaseModel):
    """Query component.

    Represents a component that can be run in a `QueryPipeline`.

    """

    partial_dict: Dict[str, Any] = Field(
        default_factory=dict, description="Partial arguments to run_component"
    )

    # TODO: make this a subclass of BaseComponent (e.g. use Pydantic)

    def partial(self, **kwargs: Any) -> None:
        """Update with partial arguments."""
        self.partial_dict.update(kwargs)

    @abstractmethod
    def set_callback_manager(self, callback_manager: Any) -> None:
        """Set callback manager."""
        # TODO: refactor so that callback_manager is always passed in during runtime.

    @property
    def free_input_keys(self) -> Set[str]:
        """Get free input keys."""
        return self.input_keys.all().difference(self.partial_dict.keys())

    @abstractmethod
    def _validate_component_inputs(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component inputs during run_component."""

    def _validate_component_outputs(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component outputs during run_component."""
        # override if needed
        return output

    def validate_component_inputs(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component inputs."""
        # make sure set of input keys == self.input_keys
        self.input_keys.validate(set(input.keys()))
        return self._validate_component_inputs(input)

    def validate_component_outputs(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component outputs."""
        # make sure set of output keys == self.output_keys
        self.output_keys.validate(set(output.keys()))
        return self._validate_component_outputs(output)

    def run_component(self, **kwargs: Any) -> Dict[str, Any]:
        """Run component."""
        kwargs.update(self.partial_dict)
        kwargs = self.validate_component_inputs(kwargs)
        component_outputs = self._run_component(**kwargs)
        return self.validate_component_outputs(component_outputs)

    async def arun_component(self, **kwargs: Any) -> Dict[str, Any]:
        """Run component."""
        kwargs.update(self.partial_dict)
        kwargs = self.validate_component_inputs(kwargs)
        component_outputs = await self._arun_component(**kwargs)
        return self.validate_component_outputs(component_outputs)

    @abstractmethod
    def _run_component(self, **kwargs: Any) -> Dict:
        """Run component."""

    async def _arun_component(self, **kwargs: Any) -> Any:
        """Run component (async)."""
        raise NotImplementedError("This component does not support async run.")

    @property
    @abstractmethod
    def input_keys(self) -> InputKeys:
        """Input keys."""

    @property
    @abstractmethod
    def output_keys(self) -> OutputKeys:
        """Output keys."""