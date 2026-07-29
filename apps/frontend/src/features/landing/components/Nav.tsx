import { useEffect, useState } from "react";

import { RoleSelectModal, useAuthContext } from "@/features/auth";

import { Logo } from "./Logo";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const { user, logout } = useAuthContext();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav className={`nav ${scrolled ? "scrolled" : ""}`}>
      <div className="wrap nav-in">
        <Logo />
        <div className="nav-links">
          <a href="#product">Product</a>
          <a href="#how">How It Works</a>
          <a href="#evidence">Evidence</a>
          <a href="#team">Team</a>
        </div>
        {user ? (
          <div className="nav-user">
            <span className="nav-user-name">
              Hi, <b>{user.full_name.split(" ")[0]}</b>
            </span>
            <button type="button" className="nav-logout" onClick={() => void logout()}>
              Log out
            </button>
          </div>
        ) : (
          <button type="button" className="nav-login" onClick={() => setRoleModalOpen(true)}>
            Login
          </button>
        )}
      </div>

      <RoleSelectModal open={roleModalOpen} onClose={() => setRoleModalOpen(false)} />
    </nav>
  );
}
