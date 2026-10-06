/**
 * Fill a text field the way a person does: by typing.
 *
 * `fireEvent.change` on a text field reaches React only when React DOM was first evaluated while a
 * DOM existed. React DOM decides that once (`isInputEventSupported`), and a test file that imports
 * `@testing-library/react` at its top evaluates it before its own `beforeAll` registers happy-dom.
 * From then on, in every later file, React watches key events instead and a dispatched `change`
 * moves the DOM value and nothing else: the same test passes alone and fails in the suite.
 * Typing works either way. Selects and file inputs take `change` in both cases and need none of this.
 */
export async function typeInto(field: Element, value: string) {
  const { default: userEvent } = await import("@testing-library/user-event");
  // The field's own document: the library's default is the one that existed when it was first imported,
  // which is none when an earlier file imported it at its top.
  const user = userEvent.setup({ document: field.ownerDocument });
  await user.clear(field);
  // Emptying a field sends no key event of its own; the key press is what the key-watching React notices.
  await user.type(field, value || "{Backspace}");
}

/** Select through the accessible popup, including the pointer events Base UI needs. */
export async function selectOption(trigger: Element, name: string) {
  const { default: userEvent } = await import('@testing-library/user-event');
  const { findByRole } = await import('@testing-library/dom');
  const user = userEvent.setup({document:trigger.ownerDocument});
  await user.click(trigger);
  await user.click(await findByRole(trigger.ownerDocument.body,'option',{name}));
}
