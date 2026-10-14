"use client";
import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";

// A dialog over the page, for a small form. Put the form's fields in <div className="dialog-body">
// and its buttons in <div className="dialog-foot">, inside one <form>.
// `dismissible={false}` keeps it open until a button in it closes it: for something that is shown
// only once, like a new account's password.
export default function Dialog({ open, title, onClose, dismissible = true, children }: {
  open: boolean;
  title: string;
  onClose: () => void;
  dismissible?: boolean;
  children: React.ReactNode;
}) {
  const box = useRef<HTMLDialogElement | null>(null);
  const heading = useId();

  useEffect(() => {
    const dialog = box.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={box} className="dialog" aria-labelledby={heading}
      onCancel={(e) => { e.preventDefault(); if (dismissible) onClose(); }}                        // Escape
      onClick={(e) => { if (dismissible && e.target === box.current) onClose(); }}                // a click beside it
      // The browser closed it by itself while it should be open: Chrome does on a second Escape,
      // even when the first was refused. One that may not be dismissed is opened again (its
      // password would be lost otherwise); one that may is closed for good.
      onClose={() => {
        if (!open) return;
        if (dismissible) onClose();
        else box.current?.showModal();
      }}
    >
      {open && (
        <>
          <div className="dialog-head">
            <h2 id={heading}>{title}</h2>
            {dismissible && <button type="button" className="icon" aria-label="Close" title="Close" onClick={onClose}><X aria-hidden /></button>}
          </div>
          {children}
        </>
      )}
    </dialog>
  );
}
