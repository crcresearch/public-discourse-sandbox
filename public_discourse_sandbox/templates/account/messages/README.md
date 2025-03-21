Why are these files in here?

We don't need allauth's toasts to appear at log in and log out. It turns out the easiest way to get rid of them is to override them with empty components. Allauth looks here for the content of those toasts and uses these rather than its default if it finds it.