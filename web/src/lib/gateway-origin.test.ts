// @vitest-environment jsdom
/**
 * A validação da origem do gateway, testada nos casos que importam.
 *
 * Duas propriedades são de segurança e não podem regredir em silêncio:
 *   1. HTTP em texto claro só para a rede do próprio usuário;
 *   2. nada de esquema executável, credencial embutida ou caminho.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  clearGatewayOrigin,
  GATEWAY_ORIGIN_STORAGE_KEY,
  gatewayOrigin,
  isPrivateHost,
  normalizeGatewayOrigin,
  setGatewayOrigin,
} from "./gateway-origin";

describe("isPrivateHost", () => {
  const privateHosts = [
    "localhost",
    "app.localhost",
    "127.0.0.1",
    "127.1.2.3",
    "10.0.0.1",
    "10.255.255.255",
    "192.168.0.10",
    "192.168.255.1",
    "172.16.0.1",
    "172.31.255.255",
    "169.254.1.1",
    "100.64.0.1",
    "meu-pc.local",
    "::1",
    "fd00::1",
    "fe80::1",
  ];

  it.each(privateHosts)("%s é privado", (host) => {
    expect(isPrivateHost(host)).toBe(true);
  });

  const publicHosts = [
    "example.com",
    "gateway.exemplo.com.br",
    "8.8.8.8",
    "1.1.1.1",
    // Vizinhos das faixas privadas que NÃO são privados — o erro clássico.
    "172.15.0.1",
    "172.32.0.1",
    "192.169.0.1",
    "11.0.0.1",
    "100.128.0.1",
    "9.255.255.255",
  ];

  it.each(publicHosts)("%s é público", (host) => {
    expect(isPrivateHost(host)).toBe(false);
  });
});

describe("normalizeGatewayOrigin", () => {
  it("aceita https em qualquer host", () => {
    expect(normalizeGatewayOrigin("https://gateway.exemplo.com")).toBe(
      "https://gateway.exemplo.com",
    );
    expect(normalizeGatewayOrigin("https://gateway.exemplo.com:8443")).toBe(
      "https://gateway.exemplo.com:8443",
    );
  });

  it("aceita http para a rede local", () => {
    expect(normalizeGatewayOrigin("http://192.168.0.10:9119")).toBe(
      "http://192.168.0.10:9119",
    );
    expect(normalizeGatewayOrigin("http://localhost:9119")).toBe(
      "http://localhost:9119",
    );
    expect(normalizeGatewayOrigin("http://meu-pc.local:9119")).toBe(
      "http://meu-pc.local:9119",
    );
  });

  it("RECUSA http para host público", () => {
    // O ponto inteiro da regra: acesso remoto se faz por túnel ou HTTPS,
    // nunca abrindo uma porta em texto claro para a internet.
    expect(normalizeGatewayOrigin("http://gateway.exemplo.com")).toBeNull();
    expect(normalizeGatewayOrigin("http://8.8.8.8:9119")).toBeNull();
  });

  it("RECUSA esquema que executa", () => {
    expect(normalizeGatewayOrigin("javascript:alert(1)")).toBeNull();
    expect(normalizeGatewayOrigin("data:text/html,<script>")).toBeNull();
    expect(normalizeGatewayOrigin("file:///etc/passwd")).toBeNull();
    expect(normalizeGatewayOrigin("ftp://exemplo.com")).toBeNull();
  });

  it("RECUSA credencial embutida", () => {
    // Viajaria em todo request e ficaria no localStorage em texto claro.
    expect(normalizeGatewayOrigin("https://user:senha@exemplo.com")).toBeNull();
    expect(normalizeGatewayOrigin("https://user@exemplo.com")).toBeNull();
  });

  it("RECUSA caminho, query e fragmento", () => {
    expect(normalizeGatewayOrigin("https://exemplo.com/dashboard")).toBeNull();
    expect(normalizeGatewayOrigin("https://exemplo.com/?token=abc")).toBeNull();
    expect(normalizeGatewayOrigin("https://exemplo.com/#/chat")).toBeNull();
  });

  it("aceita a barra final sozinha e a normaliza fora", () => {
    expect(normalizeGatewayOrigin("https://exemplo.com/")).toBe(
      "https://exemplo.com",
    );
  });

  it("adivinha o esquema quando o usuário não digita nenhum", () => {
    expect(normalizeGatewayOrigin("192.168.0.10:9119")).toBe(
      "http://192.168.0.10:9119",
    );
    expect(normalizeGatewayOrigin("gateway.exemplo.com")).toBe(
      "https://gateway.exemplo.com",
    );
  });

  it("recusa vazio e lixo", () => {
    expect(normalizeGatewayOrigin("")).toBeNull();
    expect(normalizeGatewayOrigin("   ")).toBeNull();
    expect(normalizeGatewayOrigin("://")).toBeNull();
    expect(normalizeGatewayOrigin("http://")).toBeNull();
  });
});

describe("persistência", () => {
  beforeEach(() => {
    clearGatewayOrigin();
  });

  afterEach(() => {
    clearGatewayOrigin();
  });

  it("sem nada configurado devolve string vazia — comportamento de hoje", () => {
    // Esta é a garantia de que a mudança é aditiva: com storage limpo, todas
    // as URLs continuam relativas como sempre foram.
    expect(gatewayOrigin()).toBe("");
  });

  it("grava e lê de volta normalizado", () => {
    expect(setGatewayOrigin("192.168.0.10:9119")).toBe(
      "http://192.168.0.10:9119",
    );
    expect(gatewayOrigin()).toBe("http://192.168.0.10:9119");
  });

  it("valor recusado não é gravado", () => {
    setGatewayOrigin("https://bom.exemplo.com");
    expect(setGatewayOrigin("javascript:alert(1)")).toBeNull();
    expect(gatewayOrigin()).toBe("https://bom.exemplo.com");
  });

  it("um valor inválido plantado no storage é ignorado na leitura", () => {
    // Defesa contra o storage ter sido escrito por outra versão do app, ou
    // por um script na mesma origem.
    localStorage.setItem(GATEWAY_ORIGIN_STORAGE_KEY, "javascript:alert(1)");
    expect(gatewayOrigin()).toBe("");

    localStorage.setItem(
      GATEWAY_ORIGIN_STORAGE_KEY,
      "http://gateway-publico.exemplo.com",
    );
    expect(gatewayOrigin()).toBe("");
  });

  it("clear volta ao comportamento de origem própria", () => {
    setGatewayOrigin("https://exemplo.com");
    clearGatewayOrigin();
    expect(gatewayOrigin()).toBe("");
  });
});
