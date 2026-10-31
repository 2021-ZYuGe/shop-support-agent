import { Sprout } from "lucide-react";
import { Link } from "react-router-dom";

interface BrandProps {
  to?: string;
  compact?: boolean;
}

export function Brand({ to = "/", compact = false }: BrandProps) {
  return (
    <Link className="brand" to={to} aria-label="青禾生活首页">
      <span className="brand__mark">
        <Sprout size={compact ? 18 : 21} strokeWidth={2.2} />
      </span>
      <span className="brand__text">
        <strong>青禾生活</strong>
        {!compact && <small>AFTER-SALES STUDIO</small>}
      </span>
    </Link>
  );
}
