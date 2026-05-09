export default function NotificationBanner({ message }) {
  if (!message) return null;
  return (
    <div className="notification-banner" role="alert">
      {message}
    </div>
  );
}

