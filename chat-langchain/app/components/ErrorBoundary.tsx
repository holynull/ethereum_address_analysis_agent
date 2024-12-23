// components/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(_: Error): State {
    return { hasError: false };  // 返回 false 来阻止显示错误 UI
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // 可以在这里做错误日志记录
    console.log('Error:', error);
    console.log('ErrorInfo:', errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return null; // 不显示错误UI
    }

    return this.props.children;
  }
}

export default ErrorBoundary;