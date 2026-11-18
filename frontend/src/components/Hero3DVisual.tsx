"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

export function Hero3DVisual() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [webglSupported, setWebglSupported] = useState(true);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Check prefers-reduced-motion safely
    const prefersReducedMotion =
      typeof window !== "undefined" && typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
        : false;

    // Check WebGL support safely before touching canvas context
    if (
      typeof window === "undefined" ||
      typeof document === "undefined" ||
      typeof window.WebGLRenderingContext === "undefined"
    ) {
      setWebglSupported(false);
      return;
    }

    try {
      const testCanvas = document.createElement("canvas");
      const gl = testCanvas.getContext("webgl") || testCanvas.getContext("experimental-webgl");
      if (!gl) {
        setWebglSupported(false);
        return;
      }
    } catch {
      setWebglSupported(false);
      return;
    }

    // Scene setup
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch {
      setWebglSupported(false);
      return;
    }

    const scene = new THREE.Scene();

    const width = container.clientWidth || 480;
    const height = container.clientHeight || 420;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 26;

    try {
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 2));
      container.appendChild(renderer.domElement);
    } catch {
      setWebglSupported(false);
      return;
    }

    // Main group for rotation
    const mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // 1. Core Decision Node - Wireframe Icosahedron
    const coreGeometry = new THREE.IcosahedronGeometry(4.8, 1);
    const coreMaterial = new THREE.MeshBasicMaterial({
      color: 0x10b981, // Emerald accent
      wireframe: true,
      transparent: true,
      opacity: 0.38,
    });
    const coreMesh = new THREE.Mesh(coreGeometry, coreMaterial);
    mainGroup.add(coreMesh);

    // 2. Inner Kernel - Solid glowing dodecahedron
    const innerGeometry = new THREE.DodecahedronGeometry(2.4, 0);
    const innerMaterial = new THREE.MeshBasicMaterial({
      color: 0x3b82f6, // Blue glow
      wireframe: true,
      transparent: true,
      opacity: 0.65,
    });
    const innerMesh = new THREE.Mesh(innerGeometry, innerMaterial);
    mainGroup.add(innerMesh);

    // 3. Orbiting Agent Decision Nodes
    const agentNodesCount = 6;
    const nodeGeometry = new THREE.SphereGeometry(0.45, 12, 12);
    const nodeMaterial = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
    const agentNodes: THREE.Mesh[] = [];
    const orbitRadius = 8.5;

    for (let i = 0; i < agentNodesCount; i++) {
      const angle = (i / agentNodesCount) * Math.PI * 2;
      const mesh = new THREE.Mesh(nodeGeometry, nodeMaterial);
      mesh.position.x = Math.cos(angle) * orbitRadius;
      mesh.position.y = Math.sin(angle) * (orbitRadius * 0.45);
      mesh.position.z = Math.sin(angle * 2) * 2.5;
      mainGroup.add(mesh);
      agentNodes.push(mesh);
    }

    // 4. Lattice Lines connecting core to nodes
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x10b981,
      transparent: true,
      opacity: 0.35,
    });

    const linesGroup = new THREE.Group();
    agentNodes.forEach((node) => {
      const points = [new THREE.Vector3(0, 0, 0), node.position];
      const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.Line(lineGeo, lineMaterial);
      linesGroup.add(line);
    });
    mainGroup.add(linesGroup);

    // 5. Ambient Data Particles
    const particleCount = 140;
    const particleGeometry = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
      particlePositions[i] = (Math.random() - 0.5) * 32;
      particlePositions[i + 1] = (Math.random() - 0.5) * 26;
      particlePositions[i + 2] = (Math.random() - 0.5) * 20;
    }
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));

    const particleMaterial = new THREE.PointsMaterial({
      color: 0xa7f3d0,
      size: 0.16,
      transparent: true,
      opacity: 0.6,
    });
    const particleSystem = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particleSystem);

    // Mouse interaction parallax
    let mouseX = 0;
    let mouseY = 0;
    let targetRotationX = 0;
    let targetRotationY = 0;

    const handleMouseMove = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left - rect.width / 2;
      const y = event.clientY - rect.top - rect.height / 2;
      mouseX = x / rect.width;
      mouseY = y / rect.height;
      targetRotationY = mouseX * 0.8;
      targetRotationX = -mouseY * 0.6;
    };

    window.addEventListener("mousemove", handleMouseMove);

    // Responsive resize handler
    const handleResize = () => {
      if (!container || !renderer) return;
      const newWidth = container.clientWidth;
      const newHeight = container.clientHeight;
      camera.aspect = newWidth / newHeight;
      if (newWidth < 500) {
        camera.position.z = 32; // pull camera back on mobile
      } else {
        camera.position.z = 26;
      }
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    // Animation Loop
    let animationFrameId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      if (!prefersReducedMotion) {
        const elapsedTime = clock.getElapsedTime();

        // Rotate main group smoothly
        mainGroup.rotation.y += 0.005;
        mainGroup.rotation.x += 0.002;

        // Smooth mouse damping
        mainGroup.rotation.y += (targetRotationY - mainGroup.rotation.y) * 0.04;
        mainGroup.rotation.x += (targetRotationX - mainGroup.rotation.x) * 0.04;

        // Pulse inner node
        const scale = 1 + Math.sin(elapsedTime * 2.5) * 0.08;
        innerMesh.scale.set(scale, scale, scale);

        // Animate particles slowly
        particleSystem.rotation.y = elapsedTime * 0.02;
        particleSystem.rotation.x = elapsedTime * 0.01;
      }

      renderer.render(scene, camera);
    };

    animate();

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);

      coreGeometry.dispose();
      coreMaterial.dispose();
      innerGeometry.dispose();
      innerMaterial.dispose();
      nodeGeometry.dispose();
      nodeMaterial.dispose();
      lineMaterial.dispose();
      particleGeometry.dispose();
      particleMaterial.dispose();

      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return (
    <div className="relative flex h-[380px] w-full items-center justify-center sm:h-[460px] lg:h-[500px]">
      {/* Background glow orb */}
      <div
        className="pointer-events-none absolute h-64 w-64 rounded-full bg-emerald-500/15 blur-3xl sm:h-80 sm:w-80"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute h-52 w-52 rounded-full bg-sky-500/10 blur-2xl -translate-x-12 translate-y-12"
        aria-hidden="true"
      />

      {/* 3D Canvas Container */}
      <div
        ref={containerRef}
        className="relative z-10 h-full w-full cursor-grab active:cursor-grabbing"
        title="Interactive 3D Decision Intelligence Graph (move cursor to interact)"
        aria-label="Interactive 3D Decision Intelligence Graph"
      />

      {/* Floating status badges overlay */}
      <div className="pointer-events-none absolute bottom-4 left-4 z-20 flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-background/80 px-3 py-1.5 backdrop-blur-md">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-medium text-foreground">Deterministic Causal Engine</span>
        </div>
      </div>

      <div className="pointer-events-none absolute top-4 right-4 z-20 flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2 rounded-full border border-sky-500/20 bg-background/80 px-3 py-1.5 backdrop-blur-md">
          <span className="h-2 w-2 rounded-full bg-sky-400" />
          <span className="text-muted">6 Specialized Agents In Orbit</span>
        </div>
      </div>

      {!webglSupported && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface/50 p-6 text-center text-sm text-muted">
          <span>Decision Intelligence Graph</span>
        </div>
      )}
    </div>
  );
}
