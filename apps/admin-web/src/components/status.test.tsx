import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Empty, Status } from "./status";

describe("status components", () => {
  it("renders active and inactive account states", () => {
    const { rerender } = render(<Status active />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    rerender(<Status active={false} />);
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("renders useful empty-state copy", () => {
    render(<Empty message="No reminders have been created." />);
    expect(screen.getByText("No reminders have been created.")).toBeInTheDocument();
  });
});
